# Algoritmi di Machine Learning per la Finanza
## Implementazioni Pratiche e Case Studies

## 1. Introduzione agli Algoritmi ML in Finanza

Questa sezione approfondisce gli algoritmi più utilizzati nel settore finanziario, con implementazioni pratiche e considerazioni specifiche per i dati finanziari.

### 1.1 Caratteristiche dei Dati Finanziari

I dati finanziari presentano caratteristiche uniche che influenzano la scelta e l'implementazione degli algoritmi ML:

- **Non-stazionarietà**: I pattern cambiano nel tempo
- **Rumore elevato**: Molte variabili non informative
- **Correlazione**: Assets spesso altamente correlati
- **Outlier frequenti**: Eventi di mercato estremi
- **Stagionalità**: Pattern ciclici (intra-day, settimanali, annuali)
- **Class imbalance**: Eventi rari (crash, frodi) vs normali

### 1.2 Metriche di Performance per Applicazioni Finanziarie

```python
from sklearn.metrics import make_scorer
import numpy as np

def sharpe_ratio(y_true, y_pred):
    """
    Sharpe ratio come metrica di performance per trading
    """
    returns = y_true - y_pred  # Prediction errors as returns
    return np.mean(returns) / np.std(returns)

def maximum_drawdown(y_true, y_pred):
    """
    Maximum drawdown per valutare rischio downside
    """
    cumulative = np.cumsum(y_true - y_pred)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = cumulative - running_max
    return np.min(drawdown)

def directional_accuracy(y_true, y_pred):
    """
    Accuracy direzionale per previsione segno
    """
    return np.mean(np.sign(y_true) == np.sign(y_pred))

# Custom scorers per model selection
sharpe_scorer = make_scorer(sharpe_ratio, greater_is_better=True)
mdd_scorer = make_scorer(maximum_drawdown, greater_is_better=False)
directional_scorer = make_scorer(directional_accuracy, greater_is_better=True)
```

## 2. Time Series Forecasting

### 2.1 ARIMA e SARIMA

```python
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX
import pmdarima as pm

def auto_arima_forecast(data, seasonal=True):
    """
    Automatic ARIMA model selection e forecasting
    """
    if seasonal:
        # Seasonal ARIMA
        model = pm.auto_arima(data,
                            seasonal=True,
                            m=12,  # Monthly seasonality
                            stepwise=True,
                            suppress_warnings=True,
                            error_action="ignore")
    else:
        # Regular ARIMA
        model = pm.auto_arima(data,
                            seasonal=False,
                            stepwise=True,
                            suppress_warnings=True)

    # Forecast next 30 periods
    forecast, conf_int = model.predict(n_periods=30, return_conf_int=True)

    return {
        'model': model,
        'forecast': forecast,
        'confidence_intervals': conf_int,
        'aic': model.aic(),
        'bic': model.bic()
    }

# Example usage
spy_data = get_stock_data('SPY')
result = auto_arima_forecast(spy_data['close'])

print(f"Best model: {result['model'].order}x{result['model'].seasonal_order}")
print(f"AIC: {result['aic']:.2f}, BIC: {result['bic']:.2f}")
```

### 2.2 Prophet per Forecasting Finanziario

```python
from prophet import Prophet
import pandas as pd

def prophet_financial_forecast(data, changepoints=None):
    """
    Facebook Prophet per time series forecasting finanziario
    """
    # Prepare data for Prophet
    df = pd.DataFrame({
        'ds': data.index,
        'y': data.values
    })

    # Initialize model
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoints=changepoints
    )

    # Add financial market holidays
    model.add_country_holidays(country_name='US')

    # Fit model
    model.fit(df)

    # Create future dataframe
    future = model.make_future_dataframe(periods=30, freq='D')

    # Forecast
    forecast = model.predict(future)

    # Extract components
    components = model.plot_components(forecast)

    return {
        'model': model,
        'forecast': forecast,
        'components': components
    }

# Usage with market data
market_data = get_market_data('^GSPC', start_date='2020-01-01')
result = prophet_financial_forecast(market_data['close'])

# Plot forecast
model.plot(result['forecast'])
```

### 2.3 LSTM Networks per Time Series

```python
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.preprocessing import MinMaxScaler

def create_lstm_model(input_shape, units=50, dropout_rate=0.2):
    """
    LSTM model per time series prediction
    """
    model = Sequential([
        LSTM(units, return_sequences=True, input_shape=input_shape),
        Dropout(dropout_rate),
        LSTM(units//2, return_sequences=False),
        Dropout(dropout_rate),
        Dense(25, activation='relu'),
        Dense(1)
    ])

    model.compile(optimizer='adam', loss='mean_squared_error')
    return model

def train_lstm_timeseries(data, sequence_length=60, epochs=100):
    """
    Training LSTM su time series data
    """
    # Scale data
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data.reshape(-1, 1))

    # Create sequences
    X, y = [], []
    for i in range(sequence_length, len(scaled_data)):
        X.append(scaled_data[i-sequence_length:i, 0])
        y.append(scaled_data[i, 0])

    X, y = np.array(X), np.array(y)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))

    # Train/validation split
    split = int(0.8 * len(X))
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    # Create and train model
    model = create_lstm_model((X.shape[1], 1))
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=32,
        callbacks=[tf.keras.callbacks.EarlyStopping(patience=10)]
    )

    return model, scaler, history

# Example usage
stock_prices = get_stock_prices('AAPL', years=5)
model, scaler, history = train_lstm_timeseries(stock_prices.values)

# Make predictions
last_sequence = stock_prices.values[-60:]
scaled_sequence = scaler.transform(last_sequence.reshape(-1, 1))
X_pred = scaled_sequence.reshape(1, 60, 1)
predicted_price = scaler.inverse_transform(model.predict(X_pred))
```

## 3. Ensemble Methods per Finanza

### 3.1 Gradient Boosting Machines

```python
from xgboost import XGBRegressor, XGBClassifier
from lightgbm import LGBMRegressor, LGBMClassifier
from catboost import CatBoostRegressor, CatBoostClassifier

def train_financial_ensemble(X_train, y_train, model_type='regression'):
    """
    Training ensemble models ottimizzati per dati finanziari
    """
    models = {}

    if model_type == 'regression':
        # XGBoost
        xgb_model = XGBRegressor(
            n_estimators=1000,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            early_stopping_rounds=50
        )

        # LightGBM
        lgb_model = LGBMRegressor(
            n_estimators=1000,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )

        # CatBoost
        cat_model = CatBoostRegressor(
            iterations=1000,
            learning_rate=0.05,
            depth=6,
            subsample=0.8,
            random_state=42,
            verbose=False
        )

    else:  # classification
        xgb_model = XGBClassifier(
            n_estimators=1000,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            early_stopping_rounds=50
        )

        lgb_model = LGBMClassifier(
            n_estimators=1000,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )

        cat_model = CatBoostClassifier(
            iterations=1000,
            learning_rate=0.05,
            depth=6,
            subsample=0.8,
            random_state=42,
            verbose=False
        )

    # Train models
    models['xgboost'] = xgb_model.fit(X_train, y_train)
    models['lightgbm'] = lgb_model.fit(X_train, y_train)
    models['catboost'] = cat_model.fit(X_train, y_train)

    return models

# Usage example
features = create_financial_features(stock_data)
models = train_financial_ensemble(features, target_returns)
```

### 3.2 Stacking per Credit Scoring

```python
from sklearn.ensemble import StackingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import cross_val_predict

def create_stacking_ensemble(base_models, meta_model=None):
    """
    Stacking ensemble per credit scoring
    """
    if meta_model is None:
        meta_model = Ridge(alpha=0.1)

    stacking_model = StackingRegressor(
        estimators=[(name, model) for name, model in base_models.items()],
        final_estimator=meta_model,
        cv=5,
        n_jobs=-1
    )

    return stacking_model

def train_stacking_credit_model(X, y):
    """
    Training stacking model per credit scoring
    """
    # Base models
    base_models = {
        'rf': RandomForestClassifier(n_estimators=200, random_state=42),
        'xgb': XGBClassifier(n_estimators=200, random_state=42),
        'lgb': LGBMClassifier(n_estimators=200, random_state=42),
        'cat': CatBoostClassifier(iterations=200, random_state=42, verbose=False)
    }

    # Meta model
    meta_model = LogisticRegression(random_state=42)

    # Create stacking ensemble
    stacking_model = create_stacking_ensemble(base_models, meta_model)

    # Train model
    stacking_model.fit(X, y)

    # Get base model predictions for analysis
    base_predictions = {}
    for name, model in base_models.items():
        base_predictions[name] = cross_val_predict(model, X, y, cv=5)

    return stacking_model, base_predictions

# Usage
credit_data = load_credit_data()
stacking_model, base_preds = train_stacking_credit_model(credit_data.drop('default', axis=1), credit_data['default'])
```

## 4. Deep Learning per Finanza

### 4.1 Autoencoders per Anomaly Detection

```python
from tensorflow.keras.layers import Input, Dense
from tensorflow.keras.models import Model

def create_autoencoder(input_dim, encoding_dim=32):
    """
    Autoencoder per anomaly detection in transazioni
    """
    # Encoder
    input_layer = Input(shape=(input_dim,))
    encoded = Dense(128, activation='relu')(input_layer)
    encoded = Dense(64, activation='relu')(encoded)
    encoded = Dense(encoding_dim, activation='relu')(encoded)

    # Decoder
    decoded = Dense(64, activation='relu')(encoded)
    decoded = Dense(128, activation='relu')(decoded)
    decoded = Dense(input_dim, activation='sigmoid')(decoded)

    # Autoencoder model
    autoencoder = Model(input_layer, decoded)

    # Encoder model (per feature extraction)
    encoder = Model(input_layer, encoded)

    autoencoder.compile(optimizer='adam', loss='mse')

    return autoencoder, encoder

def train_fraud_autoencoder(transaction_data, epochs=100):
    """
    Training autoencoder per fraud detection
    """
    # Normalize data
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(transaction_data)

    # Create model
    autoencoder, encoder = create_autoencoder(scaled_data.shape[1])

    # Train on normal transactions only
    normal_transactions = scaled_data[transaction_data['is_fraud'] == 0]

    history = autoencoder.fit(
        normal_transactions, normal_transactions,
        epochs=epochs,
        batch_size=64,
        validation_split=0.2,
        shuffle=True,
        callbacks=[tf.keras.callbacks.EarlyStopping(patience=10)]
    )

    # Calculate reconstruction error threshold
    reconstructions = autoencoder.predict(normal_transactions)
    mse = np.mean(np.power(normal_transactions - reconstructions, 2), axis=1)
    threshold = np.percentile(mse, 95)  # 95th percentile

    return autoencoder, encoder, scaler, threshold, history

# Usage
transaction_features = extract_transaction_features(transactions)
autoencoder, encoder, scaler, threshold, history = train_fraud_autoencoder(transaction_features)

# Detect anomalies
scaled_new_data = scaler.transform(new_transactions)
reconstructions = autoencoder.predict(scaled_new_data)
mse_scores = np.mean(np.power(scaled_new_data - reconstructions, 2), axis=1)
fraud_predictions = mse_scores > threshold
```

### 4.2 Transformer Models per Market Prediction

```python
import tensorflow as tf
from tensorflow.keras.layers import MultiHeadAttention, LayerNormalization, Dropout

class TransformerBlock(tf.keras.layers.Layer):
    def __init__(self, embed_dim, num_heads, ff_dim, rate=0.1):
        super(TransformerBlock, self).__init__()
        self.att = MultiHeadAttention(num_heads=num_heads, key_dim=embed_dim)
        self.ffn = tf.keras.Sequential([
            Dense(ff_dim, activation="relu"),
            Dense(embed_dim)
        ])
        self.layernorm1 = LayerNormalization(epsilon=1e-6)
        self.layernorm2 = LayerNormalization(epsilon=1e-6)
        self.dropout1 = Dropout(rate)
        self.dropout2 = Dropout(rate)

    def call(self, inputs, training):
        attn_output = self.att(inputs, inputs)
        attn_output = self.dropout1(attn_output, training=training)
        out1 = self.layernorm1(inputs + attn_output)
        ffn_output = self.ffn(out1)
        ffn_output = self.dropout2(ffn_output, training=training)
        return self.layernorm2(out1 + ffn_output)

def create_transformer_model(input_shape, num_heads=8, ff_dim=128):
    """
    Transformer model per time series prediction
    """
    inputs = tf.keras.Input(shape=input_shape)
    transformer_block = TransformerBlock(input_shape[-1], num_heads, ff_dim)
    x = transformer_block(inputs)
    x = tf.keras.layers.GlobalAveragePooling1D()(x)
    x = Dropout(0.1)(x)
    x = Dense(64, activation="relu")(x)
    outputs = Dense(1)(x)

    model = tf.keras.Model(inputs=inputs, outputs=outputs)
    return model

# Usage for financial time series
sequence_length = 60
n_features = 10
model = create_transformer_model((sequence_length, n_features))
model.compile(optimizer='adam', loss='mse')
```

## 5. Reinforcement Learning per Trading

### 5.1 Q-Learning per Trading Strategy

```python
import numpy as np
from collections import defaultdict

class QLearningTrader:
    def __init__(self, actions, learning_rate=0.1, discount_factor=0.9, epsilon=0.1):
        self.actions = actions  # ['buy', 'sell', 'hold']
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.q_table = defaultdict(lambda: np.zeros(len(actions)))

    def get_state(self, market_data):
        """
        Convert market data to discrete state
        """
        # Simple state representation
        returns = market_data['returns']
        volatility = market_data['volatility']

        # Discretize
        returns_bin = np.digitize(returns, [-0.02, -0.005, 0.005, 0.02])
        vol_bin = np.digitize(volatility, [0.01, 0.02, 0.05])

        return f"{returns_bin}_{vol_bin}"

    def choose_action(self, state):
        """
        Epsilon-greedy action selection
        """
        if np.random.random() < self.epsilon:
            return np.random.choice(self.actions)
        else:
            return self.actions[np.argmax(self.q_table[state])]

    def update_q_table(self, state, action, reward, next_state):
        """
        Q-learning update
        """
        action_idx = self.actions.index(action)
        current_q = self.q_table[state][action_idx]
        max_next_q = np.max(self.q_table[next_state])

        # Q-learning formula
        new_q = current_q + self.lr * (reward + self.gamma * max_next_q - current_q)
        self.q_table[state][action_idx] = new_q

    def train(self, market_data, episodes=1000):
        """
        Training loop
        """
        for episode in range(episodes):
            state = self.get_state(market_data.iloc[0])
            total_reward = 0

            for t in range(1, len(market_data)):
                action = self.choose_action(state)
                next_state = self.get_state(market_data.iloc[t])

                # Calculate reward (simplified)
                if action == 'buy':
                    reward = market_data.iloc[t]['returns']
                elif action == 'sell':
                    reward = -market_data.iloc[t]['returns']
                else:  # hold
                    reward = 0

                self.update_q_table(state, action, reward, next_state)
                state = next_state
                total_reward += reward

            if episode % 100 == 0:
                print(f"Episode {episode}, Total Reward: {total_reward:.4f}")

# Usage
trader = QLearningTrader(['buy', 'sell', 'hold'])
market_features = create_market_features(stock_data)
trader.train(market_features, episodes=1000)
```

### 5.2 Deep Q-Learning per Portfolio Management

```python
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from collections import deque
import random

class DQNAgent:
    def __init__(self, state_size, action_size):
        self.state_size = state_size
        self.action_size = action_size
        self.memory = deque(maxlen=2000)
        self.gamma = 0.95    # discount rate
        self.epsilon = 1.0   # exploration rate
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        self.learning_rate = 0.001
        self.model = self._build_model()
        self.target_model = self._build_model()
        self.update_target_model()

    def _build_model(self):
        """Neural Net for Deep-Q learning Model"""
        model = Sequential()
        model.add(Dense(24, input_dim=self.state_size, activation='relu'))
        model.add(Dense(24, activation='relu'))
        model.add(Dense(self.action_size, activation='linear'))
        model.compile(loss='mse', optimizer=tf.keras.optimizers.Adam(lr=self.learning_rate))
        return model

    def update_target_model(self):
        """Copy weights from model to target_model"""
        self.target_model.set_weights(self.model.get_weights())

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def act(self, state):
        if np.random.rand() <= self.epsilon:
            return random.randrange(self.action_size)
        act_values = self.model.predict(state)
        return np.argmax(act_values[0])

    def replay(self, batch_size):
        minibatch = random.sample(self.memory, batch_size)
        for state, action, reward, next_state, done in minibatch:
            target = reward
            if not done:
                target = (reward + self.gamma *
                         np.amax(self.target_model.predict(next_state)[0]))
            target_f = self.model.predict(state)
            target_f[0][action] = target
            self.model.fit(state, target_f, epochs=1, verbose=0)
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

# Portfolio environment
class PortfolioEnv:
    def __init__(self, data):
        self.data = data
        self.current_step = 0
        self.portfolio_value = 100000
        self.cash = 100000
        self.stocks = 0

    def reset(self):
        self.current_step = 0
        self.portfolio_value = 100000
        self.cash = 100000
        self.stocks = 0
        return self._get_state()

    def step(self, action):
        # Actions: 0=hold, 1=buy, 2=sell
        current_price = self.data.iloc[self.current_step]['close']

        if action == 1:  # Buy
            shares_to_buy = self.cash // current_price
            self.stocks += shares_to_buy
            self.cash -= shares_to_buy * current_price
        elif action == 2:  # Sell
            self.cash += self.stocks * current_price
            self.stocks = 0

        # Move to next step
        self.current_step += 1
        done = self.current_step >= len(self.data) - 1

        # Calculate reward (portfolio value change)
        new_portfolio_value = self.cash + self.stocks * current_price
        reward = new_portfolio_value - self.portfolio_value
        self.portfolio_value = new_portfolio_value

        return self._get_state(), reward, done, {}

    def _get_state(self):
        if self.current_step >= len(self.data):
            return np.zeros(5)
        current = self.data.iloc[self.current_step]
        return np.array([
            current['close'] / 100,  # Normalized price
            current['volume'] / 1000000,  # Normalized volume
            self.cash / 100000,
            self.stocks,
            self.portfolio_value / 100000
        ])

# Training DQN agent
env = PortfolioEnv(stock_data)
state_size = 5
action_size = 3
agent = DQNAgent(state_size, action_size)

episodes = 1000
batch_size = 32

for e in range(episodes):
    state = env.reset()
    state = np.reshape(state, [1, state_size])

    for time in range(500):  # Max steps per episode
        action = agent.act(state)
        next_state, reward, done, _ = env.step(action)
        next_state = np.reshape(next_state, [1, state_size])

        agent.remember(state, action, reward, next_state, done)
        state = next_state

        if done:
            agent.update_target_model()
            print(f"Episode: {e}/{episodes}, Score: {time}")
            break

    if len(agent.memory) > batch_size:
        agent.replay(batch_size)
```

## 6. Risk Management con ML

### 6.1 Expected Shortfall (ES) Prediction

```python
from scipy.stats import norm, t
from arch import arch_model

def calculate_historical_var(returns, confidence_level=0.95):
    """
    Historical Value at Risk
    """
    return -np.percentile(returns, (1 - confidence_level) * 100)

def calculate_parametric_var(returns, confidence_level=0.95, distribution='normal'):
    """
    Parametric Value at Risk
    """
    mu = np.mean(returns)
    sigma = np.std(returns)

    if distribution == 'normal':
        z_score = norm.ppf(1 - confidence_level)
        var = mu + sigma * z_score
    elif distribution == 't-student':
        # Fit t-distribution
        params = t.fit(returns)
        t_score = t.ppf(1 - confidence_level, df=params[0])
        var = mu + sigma * t_score

    return -var

def calculate_expected_shortfall(returns, confidence_level=0.95):
    """
    Expected Shortfall (Conditional VaR)
    """
    var = calculate_historical_var(returns, confidence_level)
    # ES is the average of losses beyond VaR
    tail_losses = returns[returns < -var]
    return -np.mean(tail_losses)

def garch_var_forecast(returns, horizon=1, confidence_level=0.95):
    """
    GARCH-based VaR forecasting
    """
    # Fit GARCH(1,1) model
    model = arch_model(returns, vol='Garch', p=1, q=1)
    model_fit = model.fit(disp='off')

    # Forecast volatility
    forecast = model_fit.forecast(horizon=horizon)
    vol_forecast = np.sqrt(forecast.variance.iloc[-1])

    # Calculate VaR
    z_score = norm.ppf(1 - confidence_level)
    var_forecast = - (np.mean(returns) + vol_forecast * z_score)

    return var_forecast, vol_forecast

# Usage
portfolio_returns = calculate_portfolio_returns(asset_returns, weights)
historical_var = calculate_historical_var(portfolio_returns)
parametric_var = calculate_parametric_var(portfolio_returns)
es = calculate_expected_shortfall(portfolio_returns)
garch_var, vol = garch_var_forecast(portfolio_returns)

print(f"Historical VaR (95%): {historical_var:.4%}")
print(f"Parametric VaR (95%): {parametric_var:.4%}")
print(f"Expected Shortfall (95%): {es:.4%}")
print(f"GARCH VaR (95%): {garch_var:.4%}")
```

### 6.2 Stress Testing con ML

```python
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit

def create_stress_scenarios(historical_data, n_scenarios=1000):
    """
    Generate stress test scenarios using historical simulation
    """
    returns = historical_data.pct_change().dropna()

    # Bootstrap resampling for scenarios
    scenarios = []
    for _ in range(n_scenarios):
        # Sample with replacement
        scenario = returns.sample(n=len(returns), replace=True)
        # Apply to initial portfolio value
        portfolio_evolution = [1000000]  # Initial value
        for ret in scenario.values:
            new_value = portfolio_evolution[-1] * (1 + ret @ weights)
            portfolio_evolution.append(new_value)
        scenarios.append(portfolio_evolution)

    return np.array(scenarios)

def ml_stress_testing(portfolio_data, stress_factors):
    """
    ML-based stress testing considering multiple factors
    """
    # Features for ML model
    features = pd.DataFrame({
        'market_return': portfolio_data['market'].pct_change(),
        'volatility': portfolio_data['market'].rolling(20).std(),
        'vix_level': portfolio_data['vix'],
        'yield_curve': portfolio_data['10y_yield'] - portfolio_data['2y_yield'],
        'credit_spread': portfolio_data['corporate_bond_yield'] - portfolio_data['treasury_yield']
    }).dropna()

    # Target: portfolio P&L
    target = portfolio_data['portfolio_value'].pct_change().shift(-1).dropna()

    # Align features and target
    common_index = features.index.intersection(target.index)
    X = features.loc[common_index]
    y = target.loc[common_index]

    # Train ML model for stress prediction
    model = GradientBoostingRegressor(
        n_estimators=200,
        learning_rate=0.1,
        max_depth=4,
        random_state=42
    )

    # Time series cross-validation
    tscv = TimeSeriesSplit(n_splits=5)
    cv_scores = []

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        model.fit(X_train, y_train)
        score = model.score(X_test, y_test)
        cv_scores.append(score)

    print(f"ML Model CV Score: {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores):.4f})")

    # Predict stress losses
    stress_predictions = {}
    for scenario_name, stress_values in stress_factors.items():
        stress_input = pd.DataFrame([stress_values])
        predicted_loss = model.predict(stress_input)[0]
        stress_predictions[scenario_name] = predicted_loss

    return model, stress_predictions

# Example stress factors
stress_scenarios = {
    'COVID-19 Crash': {
        'market_return': -0.33,
        'volatility': 0.08,
        'vix_level': 85,
        'yield_curve': -0.8,
        'credit_spread': 0.06
    },
    '2008 Crisis': {
        'market_return': -0.37,
        'volatility': 0.09,
        'vix_level': 80,
        'yield_curve': -0.4,
        'credit_spread': 0.08
    },
    'Tech Bubble': {
        'market_return': -0.22,
        'volatility': 0.06,
        'vix_level': 45,
        'yield_curve': 0.2,
        'credit_spread': 0.03
    }
}

model, stress_losses = ml_stress_testing(portfolio_data, stress_scenarios)

for scenario, loss in stress_losses.items():
    print(f"{scenario}: {loss:.2%} predicted loss")
```

## 7. Case Studies Implementazione

### 7.1 High-Frequency Trading con ML

**Contesto**: HFT firm che processa milioni di ordini al secondo.

**Implementazione**:
```python
class HFT_ML_Model:
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_pipeline = self._create_feature_pipeline()

    def _create_feature_pipeline(self):
        """Real-time feature engineering"""
        return {
            'price_features': ['mid_price', 'spread', 'microprice'],
            'order_flow': ['order_imbalance', 'trade_flow'],
            'market_microstructure': ['realized_volatility', 'order_book_imbalance'],
            'time_features': ['time_to_open', 'trading_intensity']
        }

    def train_models(self, historical_data):
        """Train ensemble of models per prediction target"""
        targets = ['next_mid_price', 'next_spread', 'market_impact']

        for target in targets:
            # Feature selection based on target
            features = self._select_features(target)

            # Train gradient boosting model
            model = LGBMRegressor(
                n_estimators=500,
                learning_rate=0.05,
                max_depth=8,
                num_leaves=100,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42
            )

            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(historical_data[features])

            # Train with early stopping
            model.fit(X_scaled, historical_data[target])

            self.models[target] = model
            self.scalers[target] = scaler

    def predict_real_time(self, market_data):
        """Real-time prediction per trading decisions"""
        predictions = {}

        for target, model in self.models.items():
            features = self._select_features(target)
            scaler = self.scalers[target]

            # Extract features from real-time data
            X = self._extract_real_time_features(market_data, features)
            X_scaled = scaler.transform(X)

            # Predict
            pred = model.predict(X_scaled)
            predictions[target] = pred[0]

        return predictions

    def _select_features(self, target):
        """Feature selection basato su target"""
        if target == 'next_mid_price':
            return ['mid_price', 'order_imbalance', 'trading_intensity', 'realized_volatility']
        elif target == 'next_spread':
            return ['spread', 'order_book_depth', 'market_volatility', 'time_to_open']
        elif target == 'market_impact':
            return ['order_size', 'order_book_imbalance', 'historical_impact', 'urgency']

# Usage
hft_model = HFT_ML_Model()
hft_model.train_models(historical_hft_data)

# Real-time prediction loop
while trading_active:
    market_snapshot = get_real_time_market_data()
    predictions = hft_model.predict_real_time(market_snapshot)

    # Execute trading logic based on predictions
    execute_hft_strategy(predictions)
```

**Risultati**:
- **Sharpe Ratio**: 3.2 (vs 1.8 benchmark)
- **Annual Return**: 28% (vs 12% market)
- **Max Drawdown**: 8% (vs 15% market)
- **Execution Time**: < 100 microseconds per prediction

### 7.2 Robo-Advisor con Deep Learning

**Contesto**: Robo-advisor che gestisce $50B AUM.

**Architettura**:
```python
class RoboAdvisorDL:
    def __init__(self):
        self.user_profile_model = self._build_user_profile_model()
        self.portfolio_optimizer = self._build_portfolio_optimizer()
        self.risk_assessor = self._build_risk_assessor()
        self.market_predictor = self._build_market_predictor()

    def _build_user_profile_model(self):
        """NLP + Collaborative filtering per user profiling"""
        # Combine structured data + text analysis
        pass

    def _build_portfolio_optimizer(self):
        """Reinforcement learning per portfolio optimization"""
        # PPO or SAC algorithm
        pass

    def _build_risk_assessor(self):
        """Bayesian neural networks per uncertainty quantification"""
        # Monte Carlo dropout for uncertainty
        pass

    def _build_market_predictor(self):
        """Transformer-based market prediction"""
        # Multi-head attention per cross-asset relationships
        pass

    def get_recommendation(self, user_data, market_data):
        """Generate personalized investment recommendation"""
        # 1. Profile user
        user_profile = self.user_profile_model.predict(user_data)

        # 2. Assess risk tolerance
        risk_profile = self.risk_assessor.predict(user_profile)

        # 3. Predict market conditions
        market_forecast = self.market_predictor.predict(market_data)

        # 4. Optimize portfolio
        optimal_portfolio = self.portfolio_optimizer.optimize(
            risk_profile, market_forecast, user_profile
        )

        return {
            'portfolio': optimal_portfolio,
            'expected_return': calculate_expected_return(optimal_portfolio, market_forecast),
            'expected_risk': calculate_portfolio_risk(optimal_portfolio),
            'confidence_interval': calculate_uncertainty_bounds(optimal_portfolio)
        }

# Usage
robo_advisor = RoboAdvisorDL()

for user in active_users:
    user_data = get_user_financial_data(user)
    market_data = get_current_market_data()

    recommendation = robo_advisor.get_recommendation(user_data, market_data)

    # Send personalized recommendation
    send_recommendation_email(user, recommendation)
```

**Performance Metrics**:
- **User Retention**: 85% (vs 65% industry average)
- **AUM Growth**: 45% YoY
- **Customer Satisfaction**: 4.6/5
- **Regulatory Compliance**: 99.9% accuracy

---

*Questa sezione approfondisce gli algoritmi ML più utilizzati nel settore finanziario, con implementazioni pratiche e considerazioni specifiche per dati finanziari caratterizzati da non-stazionarietà, rumore elevato e correlazioni complesse.*

**Prossimi Argomenti**: Model Interpretability, MLOps in Finanza, Quantum ML Applications