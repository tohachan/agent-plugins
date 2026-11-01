package cfp

import (
	"context"
	"database/sql"
)

// DeleteTalk is called directly by the authenticated talk-delete endpoint.
// Authentication supplies Caller; there is no middleware or database authorization check.
func DeleteTalk(ctx context.Context, db *sql.DB, c Caller, talkID string) error {
	_, err := db.ExecContext(ctx, `DELETE FROM talks WHERE id = $1`, talkID)
	return err
}
