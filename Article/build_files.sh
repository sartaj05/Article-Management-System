echo "BUILD START"
python3.11.51830 -m pip install -r requirements.txt
python3.11.51830 manage.py collectstatic --noinput --clear
echo "BUILD END"