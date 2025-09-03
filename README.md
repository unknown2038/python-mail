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
$ cd /mnt/data/Flask
$ pm2 start app.py --name "flask-app" --interpreter /mnt/data/Flask/venv/bin/python3
```


## Update sent mail helper line 150 
