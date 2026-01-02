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
	@echo "ex# python manage.py update_cinii_keywords data/cinii_keywords.json"
	@echo "ex# python manage.py update_arxiv_keywords data/arxiv_keywords.json"
	@echo "ex# python manage.py update_site --name ${SITE_NAME} --domain ${SITE_DOMAIN}"
	@echo "ex# python manage.py createsuperuser --no-input --email ${EMAIL}"

code_check:
	-isort --check .
	-black --check . | cat
	-flake8 --exclude config,migrations .
	-mypy .

compile_check:
	python manage.py check
	find . -path '*/management/commands/*.py' -not -name __init__.py -not -name 'test*' | xargs python -m py_compile 

check: compile_check code_check

test:
	python manage.py test

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
