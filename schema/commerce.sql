CREATE TABLE IF NOT EXISTS product (
  sku VARCHAR(128) NOT NULL,
  description VARCHAR(128) NOT NULL,
  price BIGINT NOT NULL,
  PRIMARY KEY (sku)
);
CREATE TABLE IF NOT EXISTS customer (
  customer_id BIGINT NOT NULL AUTO_INCREMENT,
  email VARCHAR(128) NOT NULL,
  PRIMARY KEY (customer_id)
);
CREATE TABLE IF NOT EXISTS corder (
  order_id BIGINT NOT NULL AUTO_INCREMENT,
  customer_id BIGINT NOT NULL,
  sku VARCHAR(128) NOT NULL,
  price BIGINT NOT NULL,
  PRIMARY KEY (order_id),
  KEY customer_orders (customer_id)
);
