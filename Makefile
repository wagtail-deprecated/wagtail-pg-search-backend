PHONY: test unittests flaketest

test: unittests flaketest checkmanifest checksetup

unittests:
	# Run unit tests
	python setup.py test

flaketest:
	# Check syntax and style
	flake8

checkmanifest:
	# Check if all files are included in the sdist
	check-manifest

checksetup:
	# Check longdescription and metadata
	python setup.py check -msr
