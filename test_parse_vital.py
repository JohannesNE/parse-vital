from parse_vital import Vital
import matplotlib

test_path = "test/test_intellivue_demo1.vital"

test_file = Vital(test_path)
print(test_file)

test_track1 = test_file.get_track(name="PLETH_SAT_O2")
test_track2 = test_file.get_track(name="ABP")

print(test_track1)

# Save track to file
#test_track2.save_to_file()

# Convert track to Pandas Time series
test_track2_ts = test_track2.to_pandas_ts()

test_track2_ts.plot()
matplotlib.pyplot.show()



