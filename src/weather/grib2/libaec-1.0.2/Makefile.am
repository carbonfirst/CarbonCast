ACLOCAL_AMFLAGS = -I m4
SUBDIRS = src tests
EXTRA_DIST = doc/patent.txt CMakeLists.txt cmake/config.h.in \
cmake/macros.cmake README.md README.SZIP CHANGELOG.md Copyright.txt data

sampledata = 121B2TestData
sampledata_url = https://cwe.ccsds.org/sls/docs/SLS-DC/BB121B2TestData/$(sampledata).zip
update-sampledata:
	cd $(srcdir)/data && \
	  rm -rf $(sampledata) && \
	  curl $(sampledata_url) -O && unzip $(sampledata).zip && \
	  rm -f $(sampledata).zip && \
	  cd $(sampledata)/AllOptions && mv -f test_P512n22.dat test_p512n22.dat

.PHONY: update-sampledata
