#!/bin/bash

if [ -f ~/.python/araj-venv/bin/activate ]
then
	echo "Setting virtual environment"
	source ~/.python/araj-venv/bin/activate
fi

# Get the script's directory (where categories.master lives)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CATEGORIES_FILE="$SCRIPT_DIR/categories.master"

# Process all statement formats: 0801, 1250, 5136, 8635
# Organized by year directories (2025, 2026, etc.)
# Usage: ./run_all.sh [year]  (e.g., ./run_all.sh 2025)

if [ -n "$1" ]; then
	YEARS="$SCRIPT_DIR/$1"
else
	YEARS="$SCRIPT_DIR"/20*
fi

for year in $YEARS
do
	if [ -d "$year" ]; then
		year_name=$(basename "$year")
		echo "Processing year: $year_name"

		for dir in 0801 1250 5136 8635
		do
			if [ -d "$year/$dir" ]; then
				echo "  Processing $dir"
				for pdfname in "$year/$dir"/*.pdf
				do
					if [ -f "$pdfname" ]; then
						python3 "$SCRIPT_DIR/chase_analysis.py" -m "$CATEGORIES_FILE" --csv -S "$pdfname"
					fi
				done > "$year/$dir.out"
			fi
		done
	fi
done
