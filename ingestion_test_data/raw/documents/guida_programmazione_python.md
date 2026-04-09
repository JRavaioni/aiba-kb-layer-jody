# Guida alla Programmazione Python

## Introduzione a Python

Python è un linguaggio di programmazione di alto livello, interpretato, orientato agli oggetti e con una sintassi elegante che enfatizza la leggibilità del codice. Creato da Guido van Rossum nel 1991, Python ha guadagnato popolarità grazie alla sua semplicità e versatilità.

### Caratteristiche Principali

- **Sintassi chiara e leggibile**: Il codice Python è quasi come pseudocodice
- **Interpretato**: Non richiede compilazione, esecuzione diretta
- **Multipiattaforma**: Funziona su Windows, macOS, Linux
- **Librerie estese**: Ecosystem vasto con moduli per ogni esigenza
- **Community attiva**: Supporto e risorse abbondanti

### Installazione

#### Windows
1. Scaricare Python dal sito ufficiale python.org
2. Eseguire l'installer
3. Verificare con `python --version`

#### Linux
```bash
sudo apt update
sudo apt install python3
```

#### macOS
```bash
brew install python
```

## Sintassi Base

### Variabili e Tipi di Dato

```python
# Variabili
nome = "Mario"
età = 30
altezza = 1.75
studente = True

# Tipi di dato
stringa = str("Hello")
intero = int(42)
decimale = float(3.14)
booleano = bool(True)
```

### Strutture di Controllo

#### Condizionali
```python
if età >= 18:
    print("Maggiorenne")
elif età >= 13:
    print("Adolescente")
else:
    print("Bambino")
```

#### Cicli
```python
# For loop
for i in range(5):
    print(i)

# While loop
contatore = 0
while contatore < 5:
    print(contatore)
    contatore += 1
```

### Funzioni

```python
def saluta(nome):
    """Funzione che saluta una persona."""
    return f"Ciao, {nome}!"

def calcola_area(base, altezza):
    """Calcola l'area di un rettangolo."""
    return base * altezza

# Chiamata funzioni
messaggio = saluta("Luca")
area = calcola_area(10, 5)
```

## Programmazione Orientata agli Oggetti

### Classi e Oggetti

```python
class Persona:
    def __init__(self, nome, età):
        self.nome = nome
        self.età = età
    
    def presenta(self):
        return f"Mi chiamo {self.nome} e ho {self.età} anni"

# Creazione oggetto
persona1 = Persona("Anna", 25)
print(persona1.presenta())
```

### Ereditarietà

```python
class Studente(Persona):
    def __init__(self, nome, età, corso):
        super().__init__(nome, età)
        self.corso = corso
    
    def studia(self):
        return f"{self.nome} sta studiando {self.corso}"

studente1 = Studente("Marco", 22, "Informatica")
print(studente1.presenta())
print(studente1.studia())
```

## Gestione File

### Lettura File

```python
# Lettura completa
with open('file.txt', 'r') as file:
    contenuto = file.read()
    print(contenuto)

# Lettura riga per riga
with open('file.txt', 'r') as file:
    for riga in file:
        print(riga.strip())
```

### Scrittura File

```python
# Scrittura
with open('output.txt', 'w') as file:
    file.write("Prima riga\n")
    file.write("Seconda riga\n")

# Aggiunta
with open('output.txt', 'a') as file:
    file.write("Terza riga\n")
```

## Gestione Errori

```python
try:
    risultato = 10 / 0
except ZeroDivisionError:
    print("Errore: divisione per zero")
except Exception as e:
    print(f"Errore generico: {e}")
finally:
    print("Esecuzione completata")
```

## Moduli e Librerie

### Importazione

```python
# Importazione completa
import math
print(math.sqrt(16))

# Importazione selettiva
from math import sqrt, pi
print(sqrt(25))
print(pi)

# Alias
import numpy as np
import pandas as pd
```

### Librerie Essenziali

#### NumPy - Calcoli scientifici
```python
import numpy as np

array = np.array([1, 2, 3, 4, 5])
print(array.mean())
print(array.std())
```

#### Pandas - Analisi dati
```python
import pandas as pd

data = {'Nome': ['Alice', 'Bob', 'Charlie'],
        'Età': [25, 30, 35]}
df = pd.DataFrame(data)
print(df)
print(df.describe())
```

#### Matplotlib - Grafici
```python
import matplotlib.pyplot as plt

x = [1, 2, 3, 4, 5]
y = [2, 4, 6, 8, 10]

plt.plot(x, y)
plt.xlabel('X')
plt.ylabel('Y')
plt.title('Grafico di esempio')
plt.show()
```

## Best Practices

### Stile del Codice

- Seguire PEP 8
- Usare nomi descrittivi per variabili e funzioni
- Commentare il codice complesso
- Usare docstring per funzioni e classi

### Gestione Ambiente

#### Virtual Environment
```bash
# Creazione
python -m venv mio_progetto

# Attivazione
# Windows
mio_progetto\Scripts\activate
# Linux/macOS
source mio_progetto/bin/activate

# Installazione pacchetti
pip install requests numpy pandas
```

#### Requirements.txt
```
requests==2.28.1
numpy==1.24.1
pandas==1.5.2
matplotlib==3.6.2
```

### Testing

#### Unittest
```python
import unittest

class TestCalcoli(unittest.TestCase):
    def test_addizione(self):
        self.assertEqual(2 + 2, 4)
    
    def test_sottrazione(self):
        self.assertEqual(5 - 3, 2)

if __name__ == '__main__':
    unittest.main()
```

#### Pytest
```python
def test_addizione():
    assert 2 + 2 == 4

def test_sottrazione():
    assert 5 - 3 == 2
```

## Applicazioni Pratiche

### Web Development
```python
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Benvenuto nella mia app Flask!"

if __name__ == '__main__':
    app.run(debug=True)
```

### Data Science
```python
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression

# Caricamento dati
data = pd.read_csv('dati.csv')

# Preparazione
X = data[['feature1', 'feature2']]
y = data['target']

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# Modello
model = LinearRegression()
model.fit(X_train, y_train)

# Predizione
predictions = model.predict(X_test)
```

### Automazione
```python
import os
import shutil

def organizza_file(directory):
    """Organizza file per estensione."""
    for file in os.listdir(directory):
        if os.path.isfile(os.path.join(directory, file)):
            ext = file.split('.')[-1]
            dest_dir = os.path.join(directory, ext)
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(os.path.join(directory, file), 
                       os.path.join(dest_dir, file))

organizza_file('/path/to/directory')
```

## Conclusione

Python è un linguaggio versatile adatto a principianti ed esperti. La sua semplicità permette di concentrarsi sulla risoluzione dei problemi piuttosto che sulla sintassi complessa. Con la pratica e l'esplorazione delle librerie disponibili, Python può essere utilizzato per sviluppare applicazioni web, analizzare dati, automatizzare compiti e molto altro.

Ricorda: la programmazione è un'abilità che si sviluppa con la pratica costante. Inizia con progetti piccoli e aumenta gradualmente la complessità.