# minimal Makefile to run Python unit tests
# for flux-accounting

check:
	pip3 install -r requirements.txt
	python3 -m unittest discover
