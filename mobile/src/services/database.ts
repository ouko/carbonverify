import * as SQLite from 'expo-sqlite';

const DB_NAME = 'carbonverify.db';

let db: SQLite.SQLiteDatabase | null = null;

export async function getDatabase(): Promise<SQLite.SQLiteDatabase> {
  if (!db) {
    db = await SQLite.openDatabaseAsync(DB_NAME);
    await initTables();
  }
  return db;
}

async function initTables() {
  const database = await getDatabase();

  await database.execAsync(`
    CREATE TABLE IF NOT EXISTS surveys (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL,
      household_id TEXT,
      stove_id TEXT,
      village_name TEXT,
      responses TEXT NOT NULL,
      gps_latitude REAL,
      gps_longitude REAL,
      photos TEXT,
      status TEXT DEFAULT 'draft',
      synced INTEGER DEFAULT 0,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS photos (
      id TEXT PRIMARY KEY,
      survey_id TEXT,
      local_uri TEXT NOT NULL,
      gps_latitude REAL,
      gps_longitude REAL,
      timestamp TEXT,
      synced INTEGER DEFAULT 0,
      FOREIGN KEY (survey_id) REFERENCES surveys(id)
    );

    CREATE TABLE IF NOT EXISTS sync_queue (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      entity_type TEXT NOT NULL,
      entity_id TEXT NOT NULL,
      payload TEXT NOT NULL,
      retry_count INTEGER DEFAULT 0,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_surveys_synced ON surveys(synced);
    CREATE INDEX IF NOT EXISTS idx_photos_synced ON photos(synced);
  `);
}

export async function saveSurvey(survey: any) {
  const database = await getDatabase();
  await database.runAsync(
    `INSERT OR REPLACE INTO surveys (id, project_id, household_id, stove_id, village_name, responses, gps_latitude, gps_longitude, photos, status, synced, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)`,
    [
      survey.id,
      survey.project_id,
      survey.household_id,
      survey.stove_id,
      survey.village_name,
      JSON.stringify(survey.responses),
      survey.gps_latitude,
      survey.gps_longitude,
      JSON.stringify(survey.photos || []),
      survey.status || 'draft',
      survey.synced ? 1 : 0,
    ]
  );
}

export async function getPendingSurveys() {
  const database = await getDatabase();
  return await database.getAllAsync('SELECT * FROM surveys WHERE synced = 0 ORDER BY created_at DESC');
}

export async function markSurveySynced(id: string) {
  const database = await getDatabase();
  await database.runAsync('UPDATE surveys SET synced = 1, status = ? WHERE id = ?', ['synced', id]);
}

export async function savePhoto(photo: any) {
  const database = await getDatabase();
  await database.runAsync(
    `INSERT OR REPLACE INTO photos (id, survey_id, local_uri, gps_latitude, gps_longitude, timestamp, synced)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [photo.id, photo.survey_id, photo.local_uri, photo.gps_latitude, photo.gps_longitude, photo.timestamp, photo.synced ? 1 : 0]
  );
}

export async function getPendingPhotos() {
  const database = await getDatabase();
  return await database.getAllAsync('SELECT * FROM photos WHERE synced = 0');
}

export async function addToSyncQueue(entityType: string, entityId: string, payload: any) {
  const database = await getDatabase();
  await database.runAsync(
    'INSERT INTO sync_queue (entity_type, entity_id, payload) VALUES (?, ?, ?)',
    [entityType, entityId, JSON.stringify(payload)]
  );
}

export async function getSyncQueue() {
  const database = await getDatabase();
  return await database.getAllAsync('SELECT * FROM sync_queue ORDER BY created_at ASC');
}

export async function removeFromSyncQueue(id: number) {
  const database = await getDatabase();
  await database.runAsync('DELETE FROM sync_queue WHERE id = ?', [id]);
}
