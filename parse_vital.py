# Load data from .vital files from Vital Recorder
# Vital Recorder:       https://vitaldb.net/vital-recorder
# Vital File Format:    https://vitaldb.net/docs/document?documentId=1S_orMIzhL9XlWDArqh3h4rAp_IRXJs8kL7n07vAJhU8



import gzip
from construct import *
import warnings
import io
from pathlib import Path
import collections
import textwrap
import pandas as pd

class Track:
    '''
    Object which contains all packets from one track
    '''
    def __init__(self, vital_obj, trkid):
        # Get rec from trkid
        self.info, = (trk for trk in vital_obj.track_info if trk.trkid == trkid)
        self.recs = [rec for rec in vital_obj.recs if rec.trkid == trkid]
        
        # Convert values using adc_gain and adc_offset
        for i, rec in enumerate(self.recs):
            if self.info.rec_type == 1: # Waveform
                self.recs[i]['values'].vals_real = [val * self.info.adc_gain + self.info.adc_offset for val in rec['values'].vals]
            elif self.info.rec_type == 2: # Numeric
                self.recs[i]['values'].vals_real = rec['values'].val[0] * self.info.adc_gain + self.info.adc_offset 
            elif self.info.rec_type == 5: # String (Annotation)
                self.recs[i]['values'].vals_real = rec['values'].sval
                self.recs[i]['values'].num = 1 # There is only one value (string) per rec
            else: 
                raise Exception(f'Unknown rec_type: {self.info.rec_type}')

        
    def __str__(self):
        n_recs = [rec['values'].num for rec in self.recs]
        
        return textwrap.dedent(f'''
            ======= TRACK INFO =======
            name:           {self.info.name}
            unit:           {self.info.unit}
            starttime:      {self.recs[0].dt.format()} ({self.recs[0].dt.humanize()})
            measurements:   {sum(n_recs)} in {len(n_recs)} blocks
            --------------------------
            ''')

    def to_pandas_ts(self, concat_list = True):
        '''
        Convert track to data frame with time and (real) value
        '''

        try:
            # In events srate us 0. As there is only one value per rec, it can just be set to None
            freq = f'{1000/self.info.srate}ms'
        except ZeroDivisionError:
            freq = None


        pandas_ts = []

        for rec in self.recs:
            index = pd.date_range(start = rec.dt.datetime, freq = freq, periods = rec['values'].num)
            pandas_ts.append(pd.Series(rec['values'].vals_real, index = index))
        
        if concat_list:
            pandas_ts = pd.concat(pandas_ts)

        if self.info.rec_type == 1:
            # Fix to specific frequency. Fills missing values with NaN
            pandas_ts = pandas_ts.asfreq(freq)

        return pandas_ts

    def save_to_file(self, folder_path = None, file_name = None):
        '''
        Save csv file containing track
        '''
        if file_name is None:
            file_name = Path(self.info._io.name).stem + '_' + self.info.name + '.csv'
        
        if folder_path is None:
            folder_path = 'converted'

        folder_path = Path(folder_path)

        #Create folder if it does not exist
        folder_path.mkdir(parents=True, exist_ok=True)

        file_path = folder_path / file_name

        pandas_ts = self.to_pandas_ts()
        pandas_ts.to_csv(file_path, header = False)
        
        print(f'Saved {file_path}')
        


class Vital:
    '''
    Class that holds an entire .vital file as a dict
    '''
    def __init__(self, path):
        self.load_vital(path)
        self.track_info = ListContainer([packet.data for packet in self.file.body if packet.type == 0])
        self.recs = ListContainer([packet.data for packet in self.file.body if packet.type == 1])
    
    def __str__(self):
        '''
        Human readable description when Vital object is printed
        '''
        return textwrap.dedent(f'''
            ======= VITAL FILE INFO =======
            Path:           {self.file.header._io.filename}
            Size:           {self.summed_datalen/1000.0} KB
            Format Ver.:    {self.file.header.format_ver}
            Tracks (n):     {len(self.track_info)}

            ----------- Tracks ------------
            ''') + \
            pd.DataFrame(self.track_info)[['trkid', 'name', 'unit']].to_string(index = False) + \
            textwrap.dedent('''
            -------------------------------
            ''')

    def get_track(self, trkid = None, name = None):
        '''
        Returns record. Can be called with either name or trkid.
        If both are given, they are tested to match.
        '''

        if trkid is None and name is None:
            raise ValueError('get_rec expected either trkid or name')
        
        # Get trkid if name is given
        if not name is None:
            trkid_from_name, = (x.trkid for x in self.track_info if x.name == name)

            if not trkid is None:
                assert trkid == trkid_from_name
            
            trkid = trkid_from_name
        
        return Track(self, trkid)

    def save_tracks_to_file(self, trackids = None, names = None, path = None, save_all = False):
        '''
        Save tracks to individual csv files
        '''
        if save_all:
            tracks = [self.get_track(trackid) for trackid in [track_info.trkid for track_info in self.track_info]]
        elif trackids is None and names is None:
            raise ValueError('Expected either trkids, names or save_all')
        else:
            if names is not None:
                tracks = [self.get_track(name = name) for name in names]
            else: 
                tracks = [self.get_track(trackid = trackid) for trackid in trackids]
        
        for track in tracks:
            track.save_to_file(folder_path=path)

    def load_vital(self, path):
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

        with gzip.GzipFile(path, 'rb') as f:
            # the last 4 bits of a gzip files is its unpacked size
            total_file_size = f.seek(0, io.SEEK_END)
            f.seek(0)
            header = header_str.parse_stream(f)

            # Loop until stream error
            body = ListContainer()
            completed = False
            while not completed:
                try:
                    body.append(body_str.parse_stream(f))
                except StreamError:
                    #print("End of stream reached")
                    completed = True

        # Check that all packets have been parsed
        self.summed_datalen = sum([x.datalen + 5 for x in body]) + header.headerlen + 10

        #print("Total file size: " + str(total_file_size/1000) + "kB")
        assert total_file_size == self.summed_datalen, "The summed datalen does not match the filesize"

        self.file = Container(header=header, body=body)

# When run as __main__ (from command line)
def main(args):
    try:
        vitfile = Vital(args.vitalfile)
    except FileNotFoundError as err:
        print(err)
        return

    if args.info:
        print(vitfile)
    else:
        #TODO output Save tracks
        if args.trkid is not None:
            try:
                trkid_int = [int(id) for id in args.trkid]
            except ValueError as err:
                print('Error: Expected --trkid as list of integers')
                print(err)
                return
        else:
            trkid_int = None

        vitfile.save_tracks_to_file(trackids = trkid_int, names = args.name, save_all = args.saveall, path=args.outdir)
        


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert .Vital file to .csv files')
    parser.add_argument('vitalfile', type=str, help = 'Input file (.vital)')
    parser.add_argument('--outdir', '-o', type=str, help = 'Directory for csv files (default=./converted)')
    parser.add_argument('--info', '-I', action='store_true', help = 'Info about .vital file')
    parser.add_argument('--trkid', '-t', nargs='+', help = 'Id(s) of track(s) to save')
    parser.add_argument('--name', '-n', nargs='+', help = 'Name(s) of track(s) to save')
    parser.add_argument('--saveall', action='store_true', help = 'Save all tracks')
    

    main(parser.parse_args())
