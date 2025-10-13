

all:
	python manage.py makemigrations --no-color 
	python manage.py migrate --no-color

check:
	flake8 --exclude migrations user/ || true
	flake8 --exclude migrations subscriptions/ || true
	flake8 --exclude migrations news/ || true
	flake8 --exclude migrations core/ || true

dumpdata:
	python manage.py dumpdata --exclude auth.permission --exclude contenttypes >dumpdata.json

dump_category:
	python manage.py dumpdata --indent 2 subscriptions.LargeCate
gory    subscriptions.MediumCategory

clean:
	rm -f db.sqlite3 
	find . -type d -name __pycache__ | xargs rm -rf
	rm -f */migrations/0*.py
