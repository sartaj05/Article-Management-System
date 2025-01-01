echo "BUILD START"
python3.11 -m pip install -r requirements.txt  # Ensure correct Python version
python3.11 manage.py collectstatic --noinput --clear
echo "BUILD END"
