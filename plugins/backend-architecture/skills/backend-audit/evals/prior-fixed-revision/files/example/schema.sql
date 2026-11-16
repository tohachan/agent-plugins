CREATE TABLE inbox (event_id text PRIMARY KEY);
CREATE TABLE shipments (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, order_id bigint NOT NULL);
