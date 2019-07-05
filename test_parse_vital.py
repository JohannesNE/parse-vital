from parse_vital import Vital


ipath = "/home/johannes/Dropbox/Docs/PhD/general-data-analysis/test-data/test.vital"

test_file = Vital(ipath)
print(test_file.file.header)
print(test_file.file.body[1])


