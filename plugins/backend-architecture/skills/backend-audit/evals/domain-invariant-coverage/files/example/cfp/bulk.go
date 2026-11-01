package cfp

import (
	"context"
	"database/sql"
)

// BulkAccept accepts many submitted talks at once.
func BulkAccept(ctx context.Context, db *sql.DB, c Caller, ids []string) error {
	if !Allowed("talk.bulk_accept", c.Role) {
		return ErrForbidden
	}
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for _, id := range ids {
		if _, err := tx.ExecContext(ctx, `UPDATE talks SET status = 'accepted', accepted_by = $2 WHERE id = $1 AND status = 'submitted'`, id, c.ID); err != nil {
			return err
		}
	}
	return tx.Commit()
}

// ImportTalk is one row of an invited-talks spreadsheet.
type ImportTalk struct {
	ID, EventID, SpeakerID, Title string
}

// Import creates already-accepted invited talks from a spreadsheet.
func Import(ctx context.Context, db *sql.DB, c Caller, rows []ImportTalk) error {
	if !Allowed("talk.import", c.Role) {
		return ErrForbidden
	}
	for _, r := range rows {
		if _, err := db.ExecContext(ctx, `INSERT INTO talks (id, event_id, speaker_id, title, status, accepted_by) VALUES ($1, $2, $3, $4, 'accepted', $5)`,
			r.ID, r.EventID, r.SpeakerID, r.Title, c.ID); err != nil {
			return err
		}
	}
	return nil
}
