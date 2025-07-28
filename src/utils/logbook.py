import csv
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:  # pragma: no cover - optional dependency
    gspread = None
    Credentials = None

logger = logging.getLogger(__name__)


def _append_to_csv(entry: Dict[str, Any], csv_path: str) -> None:
    os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
    file_exists = os.path.isfile(csv_path)
    
    # Define the field order to ensure consistent column ordering
    fieldnames = [
        'timestamp', 'game_id', 'crash_point', 'games_analyzed',
        # Fear & Greed Index
        'fear_greed_index', 'fear_greed_sentiment', 
        'fg_performance', 'fg_volatility', 'fg_high_multipliers', 'fg_bust_frequency',
        # Volatility details
        'volatility_regime', 'volatility_ratio', 'current_volatility', 'average_volatility', 
        'volatility_percentile',
        # Momentum indicators
        'momentum_trend', 'rsi', 'momentum_score', 'recent_average',
        # Bust frequency details
        'bust_frequency_index', 'recent_bust_rate', 'long_term_bust_rate',
        # Win rates
        'win_rate_2x', 'win_rate_3x', 'win_rate_5x',
        # Risk metrics
        'sharpe_ratio_best', 'optimal_strategy', 'max_consecutive_losses',
        # Pattern detection
        'anomaly_flag', 'z_score', 'dominant_pattern', 'pattern_cycle', 'anomaly_rate',
        # Market state
        'market_states', 'risk_level', 'opportunity_score', 'trading_recommendations'
    ]
    
    with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)


def _append_to_google_sheet(entry: Dict[str, Any], credentials_path: str,
                            sheet_id: str, worksheet: str = 'Sheet1') -> None:
    if not gspread or not Credentials:
        raise RuntimeError('gspread is not installed')
    
    # Handle credentials as either a file path or JSON string
    if credentials_path.startswith('{'):
        # It's a JSON string
        import json
        creds_dict = json.loads(credentials_path)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
    else:
        # It's a file path
        creds = Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
    
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).worksheet(worksheet)
    
    # Check if sheet is empty and add headers if needed
    try:
        first_row = sheet.row_values(1)
        if not first_row:  # Sheet is empty
            headers = list(entry.keys())
            sheet.append_row(headers, value_input_option='USER_ENTERED')
    except Exception:
        # If we can't read the first row, assume it's empty and add headers
        headers = list(entry.keys())
        sheet.append_row(headers, value_input_option='USER_ENTERED')
    
    sheet.append_row(list(entry.values()), value_input_option='USER_ENTERED')


def append_game_report(game_data: Dict[str, Any], analysis: Dict[str, Any],
                       csv_path: str = 'analysis_log.csv',
                       gs_credentials: Optional[str] = None,
                       gs_sheet_id: Optional[str] = None,
                       gs_worksheet: str = 'Sheet1') -> None:
    """Append a game analysis entry to CSV and optionally Google Sheets."""
    # Extract key metrics from the analysis
    market_psych = analysis.get('market_psychology', {})
    fear_greed = market_psych.get('fear_greed_index', {})
    fear_greed_components = fear_greed.get('components', {})
    volatility = market_psych.get('volatility_regime', {})
    momentum = market_psych.get('momentum_indicators', {})
    market_state = market_psych.get('market_state', {})
    bust_freq = market_psych.get('bust_frequency_index', {})
    
    risk_metrics = analysis.get('risk_adjusted_metrics', {})
    strategies = risk_metrics.get('strategies', {})
    optimal = risk_metrics.get('optimal_strategy', {})
    
    pattern_analysis = analysis.get('pattern_analysis', {})
    patterns = pattern_analysis.get('patterns', {})
    anomalies = pattern_analysis.get('anomalies', {})
    periodicity = patterns.get('periodicity', {})
    
    # Find best Sharpe ratio
    best_sharpe = -999
    best_sharpe_strategy = ''
    for strat_name, strat_data in strategies.items():
        sharpe = strat_data.get('risk_metrics', {}).get('sharpe_ratio', -999)
        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_sharpe_strategy = strat_name
    
    # Check if current game is anomalous
    anomalous_games = anomalies.get('anomalous_games', [])
    current_game_id = str(game_data.get('gameId', ''))
    is_anomaly = False
    z_score = 0.0
    for anomaly in anomalous_games:
        if str(anomaly.get('game_id', '')) == current_game_id:
            is_anomaly = True
            z_score = anomaly.get('z_score', 0.0)
            break
    
    # Extract max consecutive losses (use highest across strategies)
    max_losses = 0
    for strat_data in strategies.values():
        losses = strat_data.get('risk_metrics', {}).get('max_consecutive_losses', 0)
        max_losses = max(max_losses, losses)
    
    # Format market states as comma-separated string
    market_states_list = market_state.get('states', ['Normal'])
    market_states_str = ', '.join(market_states_list)
    
    entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'game_id': game_data.get('gameId'),
        'crash_point': game_data.get('crashPoint'),
        'games_analyzed': analysis.get('parameters', {}).get('games_analyzed', 0),
        
        # Fear & Greed Index with components
        'fear_greed_index': round(fear_greed.get('index', 50), 2),
        'fear_greed_sentiment': fear_greed.get('sentiment', 'Neutral'),
        'fg_performance': round(fear_greed_components.get('performance', 50), 2),
        'fg_volatility': round(fear_greed_components.get('volatility', 50), 2),
        'fg_high_multipliers': round(fear_greed_components.get('high_multipliers', 50), 2),
        'fg_bust_frequency': round(fear_greed_components.get('bust_frequency', 50), 2),
        
        # Volatility details
        'volatility_regime': volatility.get('regime', 'Normal'),
        'volatility_ratio': round(volatility.get('volatility_ratio', 1.0), 3),
        'current_volatility': round(volatility.get('current_volatility', 0), 3),
        'average_volatility': round(volatility.get('average_volatility', 0), 3),
        'volatility_percentile': round(volatility.get('percentile_rank', 50), 1),
        
        # Momentum indicators
        'momentum_trend': momentum.get('trend', 'neutral'),
        'rsi': round(momentum.get('rsi', 50), 2),
        'momentum_score': round(momentum.get('momentum_score', 0), 2),
        'recent_average': round(momentum.get('recent_average', 0), 2),
        
        # Bust frequency details
        'bust_frequency_index': round(bust_freq.get('index', 100), 2),
        'recent_bust_rate': round(bust_freq.get('recent_bust_rate', 0), 2),
        'long_term_bust_rate': round(bust_freq.get('long_term_bust_rate', 0), 2),
        
        # Strategy performance
        'win_rate_2x': round(strategies.get('2.0x', {}).get('performance', {}).get('win_rate', 0), 2),
        'win_rate_3x': round(strategies.get('3.0x', {}).get('performance', {}).get('win_rate', 0), 2),
        'win_rate_5x': round(strategies.get('5.0x', {}).get('performance', {}).get('win_rate', 0), 2),
        'sharpe_ratio_best': round(best_sharpe, 4),
        'optimal_strategy': optimal.get('recommendation', best_sharpe_strategy),
        'max_consecutive_losses': max_losses,
        
        # Pattern detection
        'anomaly_flag': is_anomaly,
        'z_score': round(z_score, 3) if is_anomaly else 0,
        'dominant_pattern': patterns.get('dominant_pattern', 'None'),
        'pattern_cycle': round(periodicity.get('dominant_period', 0), 2),
        'anomaly_rate': round(anomalies.get('anomaly_rate', 0), 3),
        
        # Market state
        'market_states': market_states_str,
        'risk_level': market_state.get('risk_level', 'Medium'),
        'opportunity_score': market_state.get('opportunity_score', 50),
        
        # Trading recommendations
        'trading_recommendations': '; '.join(market_psych.get('trading_recommendations', ['Maintain normal betting strategy']))
    }
    
    try:
        _append_to_csv(entry, csv_path)
    except Exception as e:
        logger.error(f'Failed writing log CSV: {e}')
    if gs_credentials and gs_sheet_id:
        try:
            _append_to_google_sheet(entry, gs_credentials, gs_sheet_id, gs_worksheet)
        except Exception as e:
            logger.error(f'Failed logging to Google Sheets: {e}')
