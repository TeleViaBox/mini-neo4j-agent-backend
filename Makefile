.PHONY: up down logs ps health ready seed search

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

health:
	curl -s http://localhost:8000/v1/health | jq .

ready:
	curl -s http://localhost:8000/v1/ready | jq .

seed:
	curl -s -X POST http://localhost:8000/v1/memories \
	  -H "Content-Type: application/json" \
	  -d '{"user_id":"u1","text":"I like coffee and Neo4j graph memory."}' | jq .

search:
	curl -s "http://localhost:8000/v1/memories/search?user_id=u1&q=coffee&limit=10" | jq .
