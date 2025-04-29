.PHONY: install run stop down restart logs test lint

install:
	docker-compose up --build -d

run:
	docker-compose up -d

lint:
	black .
	isort .
	pylint app/ tests/
stop:
	docker-compose stop

down:
	docker-compose down -v

restart:
	docker-compose down -v
	docker-compose up -d

logs:
	docker-compose logs -f backend

test:
	docker-compose exec backend pytest

lint:
	docker-compose exec backend pylint app

clean:
	docker-compose down --rmi all --volumes --remove-orphans

rebuild: clean install