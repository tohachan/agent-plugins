package cfp

import (
	"context"
	"database/sql"
)

// PastSpeaker is one row of the archive export of every previous edition.
type PastSpeaker struct {
	ID, Email, Phone string
	LastEventEndedOn sql.NullTime
}

// ImportSpeakers upserts every speaker from the archive of previous editions.
func ImportSpeakers(ctx context.Context, db *sql.DB, rows []PastSpeaker) error {
	for _, s := range rows {
		if _, err := db.ExecContext(ctx, `INSERT INTO speakers (id, email, phone, last_event_ended_on) VALUES ($1, $2, $3, $4)
			ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, phone = EXCLUDED.phone, last_event_ended_on = EXCLUDED.last_event_ended_on`,
			s.ID, s.Email, s.Phone, s.LastEventEndedOn); err != nil {
			return err
		}
	}
	return nil
}
