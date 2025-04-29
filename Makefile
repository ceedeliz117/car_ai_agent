.PHONY: install run stop down restart logs test lint

install:
	docker-compose up --build -d

run:
	docker-compose up -d

lint:
	docker-compose run --rm backend isort .
	docker-compose run --rm backend black .
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


clean:
	docker-compose down --rmi all --volumes --remove-orphans

rebuild: clean install