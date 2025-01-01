echo "BUILD START"
# Ensure the correct Python version
python3.11 -m pip install -r requirements.txt

# Collect static files
python3.11 manage.py collectstatic --noinput --clear

echo "BUILD END"
