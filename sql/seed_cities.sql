INSERT INTO dim_city (name, country_code, latitude, longitude, timezone) VALUES
    ('Santo Domingo',  'DO',  18.48610,  -69.93120,  'America/Santo_Domingo'),
    ('Punta Cana',     'DO',  18.58200,  -68.40550,  'America/Santo_Domingo'),
    ('La Vega',        'DO',  19.22100,  -70.52900,  'America/Santo_Domingo'),
    ('Higüey',         'DO',  18.61500,  -68.70800,  'America/Santo_Domingo'),
    ('New York',       'US',  40.71280,  -74.00600,  'America/New_York'),
    ('Denver',         'US',  39.73920,  -104.99030, 'America/Denver'),
    ('Salt Lake City', 'US',  40.76080,  -111.89100, 'America/Denver'),
    ('Miami',          'US',  25.76170,  -80.19180,  'America/New_York'),
    ('Beijing',        'CN',  39.90420,  116.40740,  'Asia/Shanghai'),
    ('Shibuya',        'JP',  35.65950,  139.70050,  'Asia/Tokyo'),
    ('Madrid',         'ES',  40.41680,  -3.70380,   'Europe/Madrid'),
    ('London',         'GB',  51.50740,  -0.12780,   'Europe/London'),
    ('Reykjavik',      'IS',  64.14660,  -21.94260,  'Atlantic/Reykjavik'),
    ('Athens',         'GR',  37.98380,  23.72750,   'Europe/Athens')
ON CONFLICT (name, country_code) DO UPDATE SET
    latitude  = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    timezone  = EXCLUDED.timezone;