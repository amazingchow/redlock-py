.PHONY: deps
deps:
	@pip freeze > requirements.txt

.PHONY: lint
lint:
	@pyflakes redlock/__init__.py
	@pycodestyle redlock/__init__.py --ignore=E402,E501,W293,E266,E722
