#!/bin/bash

echo "Setting virtual environment"

source ~/.python/araj-venv/bin/activate

#Run all 0801

for dir in 0801 5136
do
	echo "Processing $dir"
	for pdfname in $dir/*.pdf 
	do
		python3 chase_analysis.py -m categories.master --csv -S $pdfname 
	done > $dir.out
done
