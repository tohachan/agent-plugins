CREATE TABLE speakers (
  id uuid PRIMARY KEY,
  email text NOT NULL,
  phone text,                     -- NULL once deleted
  last_event_ended_on date
);
CREATE TABLE talks (
  id uuid PRIMARY KEY,
  event_id uuid NOT NULL,
  speaker_id uuid NOT NULL REFERENCES speakers(id),
  title text NOT NULL,
  status text NOT NULL CHECK (status IN ('submitted','accepted','waitlisted','declined','scheduled','withdrawn')),
  accepted_by uuid
);
