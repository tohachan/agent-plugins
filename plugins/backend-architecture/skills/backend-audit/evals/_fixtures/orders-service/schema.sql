-- Authoritative schema for this synthetic fixture. No external migrations or auth controls.
CREATE TABLE products (id bigint PRIMARY KEY, stock integer NOT NULL);
CREATE TABLE orders (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id bigint, product_id bigint, qty integer, status text);
CREATE TABLE order_items (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, order_id bigint);
CREATE TABLE shipments (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, order_id bigint NOT NULL);
