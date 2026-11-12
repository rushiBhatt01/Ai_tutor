// Only runs against an empty volume. Existing databases require an explicit
// reviewed migration; never delete their volumes to make initialization rerun.
db = db.getSiblingDB("video_tutorials");
db.createUser({
  user: process.env.MONGO_APP_USER,
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: [{ role: "readWrite", db: "video_tutorials" }],
});
