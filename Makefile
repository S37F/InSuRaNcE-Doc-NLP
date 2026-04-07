install:
	pip install -r requirements.txt

download-model:
	python -m spacy download en_core_web_lg

run:
	streamlit run app.py

clean:
	python -c "import shutil; shutil.rmtree('__pycache__', ignore_errors=True)"
