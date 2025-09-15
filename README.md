# Python Mail Flask App

## Setup

1. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the Flask app:
   ```bash
   python app.py
   ```

The app will be available at [http://127.0.0.1:5000/](http://127.0.0.1:5000/) 


###  move in to venv

# install venv
```bash
$ python -m venv venv
```
# Linux
```bash
$ source venv/bin/activate
```
# Window
```bash
$ venv\Scripts\activate
```



### come out from venv

# Linux
```bash
$ deactivate
```
# Window
```bash
$ deactivate
```

### flask app start script in pm2
```bash
$ pm2 start "hypercorn app:app --bind 127.0.0.1:8001 --workers 1 --log-level debug" --name python-app
```


## Update sent mail helper line 150 
