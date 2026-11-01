package cfp

import (
	"context"
	"database/sql"
)

// PurgePhones enforces RET-1 daily.
func PurgePhones(ctx context.Context, db *sql.DB) (int64, error) {
	res, err := db.ExecContext(ctx, `UPDATE speakers SET phone = NULL
		WHERE phone = '' AND last_event_ended_on < now() - interval '6 months'`)
	if err != nil {
		return 0, err
	}
	return res.RowsAffected()
}
