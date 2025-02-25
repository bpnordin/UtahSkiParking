### What is this?
This is a python program that will help you get parking at some Utah Ski resorts. Currently Alta, Brighton, and Solitude. But adding
anything that uses the HONK website is trivial.
### Instructions on Use
- make sure that you have an account with the ski resort parking webstie. Also associated with the account will have to be a credit card and a vehicle.
I haven't created the tools to add a credit card or a vehicle because I already had those, and it saves them accross everything i.e your account on Alta Parking
is the same account as Brighton Parking and Solitide Parking
- clone repo ```git clone https://github.com/bpnordin/UtahSkiParking.git```
- enter your username and password in the ```.env.example``` file
    - optionally add a push bullet API key. This is helpful to know exaclty when the program finished. Alough you do also get an email
- rename ```.env.example``` to ```.env``` (on windows you have to make sure that there is no other file extension on it. windows be weird about it)
- install requirements
    - I recommend installing (uv)[https://github.com/astral-sh/uv]
    - run ```uv sync```
    - activate the virtual env python (```source .venv/bin/activate``` on mac/linux, something similar on windows)
- run ```python parking.py```, wait and reap benefits

I think the instructions on the command line after that are self explanitory, but essentially pick the ski resort and the date



