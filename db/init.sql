-- Schema initialization for PawCoach PostgreSQL (AP Edge-Cloud)
-- Stores dogs, progress, schedules, highlights, moments, leaderboard_entries, and device_settings

CREATE TABLE IF NOT EXISTS dogs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    pronoun TEXT NOT NULL DEFAULT 'he',
    initial TEXT NOT NULL,
    color TEXT NOT NULL,
    image TEXT NOT NULL,
    breed TEXT NOT NULL,
    age TEXT NOT NULL,
    weight TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 700,
    rank INTEGER NOT NULL DEFAULT 10,
    city TEXT NOT NULL DEFAULT 'Bucharest',
    streak INTEGER NOT NULL DEFAULT 1,
    success7d DOUBLE PRECISION NOT NULL DEFAULT 80,
    reaction TEXT NOT NULL DEFAULT '1.0 s',
    successes_today INTEGER NOT NULL DEFAULT 0,
    treats_today INTEGER NOT NULL DEFAULT 0,
    treat_limit INTEGER NOT NULL DEFAULT 25,
    week JSONB NOT NULL,
    exercises JSONB NOT NULL,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    id SERIAL PRIMARY KEY,
    dog TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    when_text TEXT NOT NULL,
    sessions INTEGER NOT NULL DEFAULT 1,
    max_treats INTEGER NOT NULL DEFAULT 10,
    is_on BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS highlights (
    id SERIAL PRIMARY KEY,
    ts DOUBLE PRECISION NOT NULL,
    dog_id TEXT REFERENCES dogs(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    exercise_id TEXT,
    value DOUBLE PRECISION,
    clip_path TEXT,
    duration_s DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS moments (
    id SERIAL PRIMARY KEY,
    dog_name TEXT NOT NULL,
    dog_breed TEXT,
    dog_image TEXT,
    caption TEXT NOT NULL,
    video_url TEXT NOT NULL,
    likes_count INTEGER NOT NULL DEFAULT 0,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS moment_likes (
    moment_id INTEGER NOT NULL REFERENCES moments(id) ON DELETE CASCADE,
    client_id TEXT NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (moment_id, client_id)
);

CREATE TABLE IF NOT EXISTS leaderboard_entries (
    category TEXT NOT NULL,
    scope TEXT NOT NULL,
    rank INTEGER NOT NULL,
    dog_id TEXT NOT NULL,
    name TEXT NOT NULL,
    breed TEXT NOT NULL,
    area TEXT NOT NULL,
    color TEXT NOT NULL,
    image TEXT NOT NULL,
    value TEXT NOT NULL,
    move TEXT NOT NULL,
    is_mine BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (category, scope, rank)
);

CREATE TABLE IF NOT EXISTS device_settings (
    name TEXT PRIMARY KEY,
    data JSONB NOT NULL
);

-- Indexes for performance & random selection under high load (CAP AP)
CREATE INDEX IF NOT EXISTS idx_moments_active_id ON moments (id) WHERE archived = FALSE;
CREATE INDEX IF NOT EXISTS idx_moment_likes_moment ON moment_likes (moment_id);
CREATE INDEX IF NOT EXISTS idx_leaderboard_cat_rank ON leaderboard_entries (category, scope, rank);

-- Seed Initial Data
INSERT INTO dogs (id, name, pronoun, initial, color, image, breed, age, weight, score, rank, city, streak, success7d, reaction, successes_today, treats_today, treat_limit, week, exercises, archived, created_at)
VALUES
    ('bruno', 'Bruno', 'he', 'B', '#F29E6D', '/dogs/bruno.jpg', 'Labrador', '3 yrs', '31 kg', 912, 7, 'Bucharest', 12, 86, '0.9 s', 16, 14, 35, '[62, 68, 66, 72, 76, 80, 86]', '[{"id":"down","name":"Down","stage":"learn","moments":18,"goal":30,"startedAgo":"4 days ago","schedule":"Daily, 10:00–17:00","limitNote":"max 10 treats · one every 30 min","caught":[["14:32","Lay down by the couch"],["12:05","Lay down after playtime"],["10:48","Lay down by the window"]]},{"id":"sit","name":"Sit","stage":"train","rate":94,"level":5,"detail":"Holds 2.5 s · one more level to master it"},{"id":"stand","name":"Stand","stage":"train","rate":88,"level":3,"detail":"Holds 1.5 s"},{"id":"stay","name":"Stay","stage":"next","detail":"Starts once he masters “Sit”"}]', FALSE, EXTRACT(EPOCH FROM NOW())),
    ('luna', 'Luna', 'she', 'L', '#A9C9A4', '/dogs/luna.jpg', 'Border Collie', '2 yrs', '17 kg', 948, 3, 'Bucharest', 21, 91, '0.7 s', 12, 9, 24, '[80, 78, 85, 83, 88, 91, 89]', '[{"id":"paw","name":"Paw","stage":"learn","moments":7,"goal":30,"startedAgo":"2 days ago","schedule":"Weekends, 12:00–16:00","limitNote":"max 8 treats · one every 30 min","caught":[["11:20","Gave her paw while begging"],["09:02","Lifted her paw at the door"]]},{"id":"down","name":"Down","stage":"train","rate":90,"level":4,"detail":"Holds 2.0 s"},{"id":"stay","name":"Stay","stage":"train","rate":82,"level":3,"detail":"Holds 6 s · goal 15 s"},{"id":"sit","name":"Sit","stage":"mastered","rate":98,"level":6,"detail":"Mastered · quick refresher weekly"}]', FALSE, EXTRACT(EPOCH FROM NOW())),
    ('toby', 'Toby', 'he', 'T', '#B9CFE6', '/dogs/toby.jpg', 'Beagle', '8 mos', '9 kg', 604, 41, 'Bucharest', 5, 58, '1.8 s', 5, 5, 18, '[40, 44, 51, 49, 55, 58, 63]', '[{"id":"sit","name":"Sit","stage":"learn","moments":24,"goal":30,"startedAgo":"6 days ago","schedule":"Mon–Fri, 09:00–18:00","limitNote":"max 12 treats · one every 30 min","caught":[["15:10","Sat by the food bowl"],["13:44","Sat when the door opened"],["10:02","Sat in his bed"]]},{"id":"down","name":"Down","stage":"next","detail":"Starts once he learns “Sit”"}]', FALSE, EXTRACT(EPOCH FROM NOW()))
ON CONFLICT (id) DO NOTHING;

INSERT INTO schedules (id, dog, type, title, when_text, sessions, max_treats, is_on)
VALUES
    (1, 'bruno', 'learn', 'Bruno · Down', 'Daily, 10:00–17:00', 1, 10, TRUE),
    (2, 'toby', 'learn', 'Toby · Sit', 'Mon–Fri, 09:00–18:00', 1, 12, TRUE),
    (3, 'bruno', 'train', 'Bruno · Sit and Stand', 'Daily, 08:00 and 18:30', 2, 10, TRUE),
    (4, 'luna', 'train', 'Luna · Down and Stay', 'Daily, 18:30', 1, 10, TRUE),
    (5, 'luna', 'learn', 'Luna · Paw', 'Weekends, 12:00–16:00', 1, 8, FALSE)
ON CONFLICT (id) DO NOTHING;

INSERT INTO moments (id, dog_name, dog_breed, dog_image, caption, video_url, likes_count, created_at)
VALUES
    (1, 'Bruno', 'Labrador', '/dogs/bruno.jpg', 'Mastering the ultimate slow sit roll 🎾', '/moments/dog1.mp4', 142, EXTRACT(EPOCH FROM NOW())),
    (2, 'Luna', 'Border Collie', '/dogs/luna.jpg', 'Wait for the sudden jump celebration! ✨', '/moments/dog2.mp4', 289, EXTRACT(EPOCH FROM NOW()) - 3600),
    (3, 'Toby', 'Beagle', '/dogs/toby.jpg', 'When the treat dispenser sound makes you freeze 🍪', '/moments/dog4.mp4', 95, EXTRACT(EPOCH FROM NOW()) - 7200),
    (4, 'Rocky', 'Malinois', '/dogs/rocky.jpg', 'Perfect posture check in 0.4 seconds flat ⚡', '/moments/dog_labradoodle_stand.webm', 310, EXTRACT(EPOCH FROM NOW()) - 10800),
    (5, 'Oscar', 'Corgi', '/dogs/oscar.jpg', 'Nap posture classification: 100% relaxed 💤', '/moments/dog_laying_relax.webm', 418, EXTRACT(EPOCH FROM NOW()) - 14400),
    (6, 'Bella', 'Golden Retriever', '/dogs/bella.jpg', 'Spins like a whirlwind when hearing good boy! 🌪️', '/moments/dog_spin_standing.webm', 523, EXTRACT(EPOCH FROM NOW()) - 18000)
ON CONFLICT (id) DO NOTHING;

INSERT INTO device_settings (name, data)
VALUES
    ('feeder', '{"online": true, "hopper": 68, "portion": "small"}'),
    ('camera', '{"online": true, "nightVision": true, "microphone": false, "speaker": true}')
ON CONFLICT (name) DO NOTHING;
