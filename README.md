# Parse and export tracks from .vital binary file

This python module parses binary files recorded by [Vital Recorder](https://vitaldb.net/vital-recorder) (.vital).

Parsing is done using [Construct](https://construct.readthedocs.io/en/latest/).

> ⚠️ **Warning:** This code has only been sporadically tested on a limited set of test data. Please validate converted files. **For most usecases, saving the file as EDF from Vital Lab would be recommended instead.**

For large files (above a few MB) the program is very slow. Using pypy speeds things up by a factor of 10-100.

## Examples

### Create a Vital object
`vital = Vital('path/to/file.vital')` 

### Show file info
`print(vital)` 

```
======= VITAL FILE INFO =======
Path:           test/test_intellivue_demo1.vital
Size:           53.19 KB
Format Ver.:    3
Tracks (n):     16

----------- Tracks ------------
 trkid            name  unit
     1        NIBP_SYS  mmHg
     2        NIBP_DIA  mmHg
     3       NIBP_MEAN  mmHg
     4         NIBP_HR  /min
     5          ECG_HR  /min
     6              RR  /min
     7        ABP_MEAN  mmHg
     8         ABP_SYS  mmHg
     9         ABP_DIA  mmHg
    10              HR  /min
    11    PLETH_SAT_O2     %
    12        PLETH_HR  /min
    13  PLETH_PERF_REL      
    14          ECG_II    mV
    15           PLETH      
    16             ABP  mmHg
-------------------------------
```

### Return object containing a single track
`vital_track = vital.get_track(name = 'track_name')` 

or `vital_track = vital.get_track(trkid = trkid)` 

### Show track info
`print(vital_track)` 

```
======= TRACK INFO =======
name:           PLETH_SAT_O2
unit:           %
starttime:      2019-06-27 11:14:16+00:00 (2 months ago)
measurements:   25 in 25 blocks
--------------------------
```

### Convert track to Pandas time series object
`vital_track.to_pandas_ts()` 

### Save track to CSV file
`vital_track.save_to_file('dir_path/')` 

## Command line interface
`$ python3 ./parse_vital --help`

```
usage: parse_vital.py [-h] [--outdir OUTDIR] [--info]
                      [--trkid TRKID [TRKID ...]] [--name NAME [NAME ...]]
                      [--saveall]
                      vitalfile

Convert .Vital file to .csv files

positional arguments:
  vitalfile             Path to input file (.vital)

optional arguments:
  -h, --help            show this help message and exit
  --outdir OUTDIR, -o OUTDIR
                        Directory for csv files (default=./converted)
  --info, -I            Info about .vital file
  --trkid TRKID [TRKID ...], -t TRKID [TRKID ...]
                        Id(s) of track(s) to save
  --name NAME [NAME ...], -n NAME [NAME ...]
                        Name(s) of track(s) to save
  --saveall             Save all tracks
```
