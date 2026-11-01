package cfp

import (
	"context"
	"database/sql"
	"errors"
)

var ErrForbidden = errors.New("forbidden")

type Caller struct {
	ID   string
	Role Role
}

// Accept accepts one submitted talk. CONFLICT-1: never one's own talk.
func Accept(ctx context.Context, db *sql.DB, c Caller, talkID string) error {
	if !Allowed("talk.accept", c.Role) {
		return ErrForbidden
	}
	var speaker string
	if err := db.QueryRowContext(ctx, `SELECT speaker_id FROM talks WHERE id = $1 AND status = 'submitted'`, talkID).Scan(&speaker); err != nil {
		return err
	}
	if speaker == c.ID {
		return ErrForbidden
	}
	_, err := db.ExecContext(ctx, `UPDATE talks SET status = 'accepted', accepted_by = $2 WHERE id = $1 AND status = 'submitted'`, talkID, c.ID)
	return err
}
