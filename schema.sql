CREATE TABLE IF NOT EXISTS price_predictions (
    delivery_date DATE,            -- Např. '2024-03-07'
    period INTEGER,                  -- 1 až 96 (nebo 100)
    predicted_price DECIMAL(10, 2),
    actual_price DECIMAL(10, 2),
    PRIMARY KEY (delivery_date, period) -- Složený klíč: Unikátní dvojice
);
