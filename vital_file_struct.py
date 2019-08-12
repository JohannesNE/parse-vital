from construct import *
import collections

# Data types
DWORD = Int32ul
WORD = Int16ul
short = Int16sl
long_ = Int32sl
float_ = Float32l
double_ = Float64l
String = PascalString(DWORD, "UTF-8")  # String preceded by length Int.

# Track format dict, used to lookup format by trkid
trk_format = {}

def save_format_hook(obj, ctx):
    trk_format.update(
        {obj["trkid"]: obj}
    )

# Packet structures
devinfo_str = Struct(
    "devid" / DWORD,
    "typename" / String,
    "devname" / String,
    "port" / String
)

# Trkinfo structure
trkinfo_str = Struct(
    "trkid" / WORD,
    "rec_type" / Byte,
    # Code only tested for float(1) and WORD(6). Others should work as well.
    "recfmt" / OneOf(Byte, [1, 6]),
    "name" / String,
    "unit" / String,
    "minval" / float_,
    "maxval" / float_,
    "color" / Array(4, Byte),  # Color
    "srate" / float_,
    "adc_gain" / double_,
    "adc_offset" / double_,
    "montype" / Byte,
    "devid" / DWORD
)

# CMD sructure
cmd_str = Struct(
    "cmd" / Byte,
    "cmd_str" / Computed(lambda this: collections.defaultdict(lambda: 'Unknown CMD', {5: 'ORDER', 6: 'RESET_EVENTS'})[this.cmd]),
    "cnt" / If(this.cmd == 5, WORD),
    "trkids" / If(this.cmd == 5, WORD[this.cnt]),
)

recfmt_str = Switch(this.recfmt,
                    {
                        # Recfmt
                        1: float_[this.num],
                        2: double_[this.num],
                        # Actually char, but does not seemn to be used
                        3: Byte[this.num],
                        4: Byte[this.num],
                        5: short[this.num],
                        6: WORD[this.num],
                        7: long_[this.num],
                        8: DWORD[this.num]
                    },
                    default="Unknown recfmt")

# Rec types
rec_wav_str = Struct(
    # Substruct under REC
    "num" / DWORD,
    "recfmt" / Computed(lambda this: trk_format[this._.trkid].recfmt),
    "vals" / recfmt_str
)

rec_num_str = Struct(
    "recfmt" / Computed(lambda this: trk_format[this._.trkid].recfmt),
    "num" / Computed(1),
    "val" / recfmt_str
)

rec_str_str = Struct(
    "unused" / DWORD,
    "sval" / String
)

# Record structure
rec_str = Struct(
    "infolen" / WORD,
    "dt" / Timestamp(double_, 1, 1970),  # Datetime as unix timestamp
    "trkid" / WORD,
    "rec_type" / Computed(lambda this: trk_format[this.trkid].rec_type),
    "name" / Computed(lambda this: trk_format[this.trkid].name),
    "values" / Switch(this.rec_type,
                    {
                        # WAV type
                        1: Padded(this._.datalen - this.infolen - 2, rec_wav_str),
                        # NUM type
                        2: Padded(this._.datalen - this.infolen - 2, rec_num_str),
                        # STR type
                        5: Padded(this._.datalen - this.infolen - 2, rec_str_str),
                    },
                    default=Byte[this._.datalen - this.infolen - 2]
                    )

)

# Header
header_str = Struct(
    "sig" / Const(b'VITA'),
    "format_ver" / DWORD,
    "headerlen" / WORD,
    "tzbias" / short,
    "inst_id" / DWORD,
    "prog_ver" / DWORD
)

# Body
body_str = Struct(
    "type" / OneOf(Byte, [0, 1, 9, 6]),
    "type_str" /
    Computed(lambda this: {0: 'TRKINFO', 1: 'REC',
                        6: 'CMD', 9: 'DEVINFO'}[this.type]),
    "datalen" / DWORD,
    "data" / Switch(this.type,
                    {
                        # Save Devinfo, For some reason needs padding to match datalen
                        9: Padded(this.datalen, devinfo_str),
                        # SAVE_TRKINFO
                        0: Padded(this.datalen, trkinfo_str) * save_format_hook,
                        # SAVE_REC
                        1: Padded(this.datalen, rec_str),
                        6: Padded(this.datalen, cmd_str), # SAVE_CMD
                    },
                    default=Padding(this.datalen))  # Skip data of len datalen if type is unknown
    
)