-- init_db.sql (unchanged)
CREATE TABLE IF NOT EXISTS owners (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE,
  name TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pets (
  id SERIAL PRIMARY KEY,
  owner_id INTEGER REFERENCES owners(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  species TEXT NOT NULL,
  breed TEXT,
  color TEXT,
  age INTEGER,
  weight_kg NUMERIC,
  length_cm NUMERIC,
  microchip_id TEXT,
  vaccination_notes TEXT,
  special_needs TEXT,
  photo_file_id TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kennels (
  id SERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  size TEXT NOT NULL,
  daily_price NUMERIC NOT NULL,
  is_active BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS foods (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  unit_price NUMERIC NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
  id SERIAL PRIMARY KEY,
  pet_id INTEGER REFERENCES pets(id) ON DELETE CASCADE,
  kennel_id INTEGER REFERENCES kennels(id),
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  food_id INTEGER REFERENCES foods(id),
  food_quantity INTEGER DEFAULT 1,
  feeding_frequency_per_day INTEGER DEFAULT 2,
  services TEXT,
  estimated_price NUMERIC,
  paid BOOLEAN DEFAULT false,
  payment_provider TEXT,
  payment_reference TEXT,
  created_at TIMESTAMP DEFAULT now()
);

-- seed kennels and foods
INSERT INTO kennels (code, size, daily_price) VALUES
('K1-S', 'small', 3),
('K2-M', 'medium', 5),
('K3-L', 'large', 8)
ON CONFLICT DO NOTHING;

INSERT INTO foods (name, unit_price) VALUES
('Basic Kibble', 1),
('Premium Kibble', 3),
('Wet Food Can', 2)
ON CONFLICT DO NOTHING;
