CREATE TABLE IF NOT EXISTS customer_seq (
  id INT NOT NULL, next_id BIGINT NOT NULL, cache BIGINT NOT NULL, PRIMARY KEY (id)
) COMMENT 'vitess_sequence';
CREATE TABLE IF NOT EXISTS order_seq (
  id INT NOT NULL, next_id BIGINT NOT NULL, cache BIGINT NOT NULL, PRIMARY KEY (id)
) COMMENT 'vitess_sequence';
