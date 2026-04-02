run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests -q

transform:
	python ../scripts/dataset_transform.py

kb-build:
	python ../scripts/kb_build.py
