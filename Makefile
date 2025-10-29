

all:
	python manage.py makemigrations --no-color 
	python manage.py migrate --no-color

init: all
	echo "ex# python manage.py update_categories data/categories.json"
	echo "ex# python manage.py update_site --name NAME --domain DOMAIN"
	echo "ex# python manage.py createsuperuser --no-input --email EMAIL"

check:
	flake8 --exclude migrations user/ || true
	flake8 --exclude migrations subscriptions/ || true
	flake8 --exclude migrations news/ || true
	flake8 --exclude migrations core/ || true

dumpdata:
	python manage.py dumpdata --exclude auth.permission --exclude contenttypes >dumpdata.json

dump_category:
	python manage.py dumpdata --indent 2 subscriptions.LargeCategory subscriptions.MediumCategory

clean:
	rm -f db.sqlite3 
	find . -type d -name __pycache__ | xargs rm -rf
	rm -f */migrations/0*.py
