#
SITE_NAME=SITE_NAME
SITE_DOMAIN=SITE_DOMAIN
EMAIL=EMAIL

all:
	python manage.py makemigrations --no-color 
	python manage.py migrate --no-color

init: all
	@echo
	@echo "ex# python manage.py update_categories data/categories.json"
	@echo "ex# python manage.py update_site --name ${SITE_NAME} --domain ${SITE_DOMAIN}"
	@echo "ex# python manage.py createsuperuser --no-input --email ${EMAIL}"

check:
	flake8 --exclude migrations users/ || true
	flake8 --exclude migrations subscriptions/ || true
	flake8 --exclude migrations news/ || true
	flake8 --exclude migrations core/ || true

dumpdata:
	python manage.py dumpdata --exclude auth.permission --exclude contenttypes >dumpdata.json

dump_category:
	python manage.py dumpdata --indent 2 subscriptions

loaddata:
	python manage.py loaddata dumpdata.json

clean:
	find . -type d -name __pycache__ | xargs rm -rf

distclean: clean
	rm -f db.sqlite3 
	find . -path '*/migrations/*.py' -not -name __init__.py | xargs rm -rf
