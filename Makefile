PHONY: test unittests flaketest

test: unittests flaketest

unittests:
	# Run unit tests
	python setup.py test

flaketest:
	# Check syntax and style
	flake8
