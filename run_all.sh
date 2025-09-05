#!/bin/bash

if [ -f ~/.python/araj-venv/bin/activate ]
then
	echo "Setting virtual environment"
	source ~/.python/araj-venv/bin/activate
fi

# Process all statement formats: 0801, 1250, 5136, 8635

for dir in 0801 1250 5136 8635
do
	echo "Processing $dir"
	for pdfname in $dir/*.pdf 
	do
		python3 chase_analysis.py -m categories.master --csv -S $pdfname 
	done > $dir.out
done
