package cfp

import (
	"context"
	"database/sql"
)

// transitions lists, per status, the statuses a program chair may move a talk to.
var transitions = map[string][]string{
	"submitted": {"accepted", "waitlisted", "declined"},
	"accepted":  {"scheduled"},
	// waitlisted: kept in reserve in case an accepted speaker drops out.
}

// Move changes a talk's status if the transition is allowed.
func Move(ctx context.Context, db *sql.DB, c Caller, talkID, from, to string) error {
	if !Allowed("talk.move", c.Role) {
		return ErrForbidden
	}
	ok := false
	for _, t := range transitions[from] {
		if t == to {
			ok = true
		}
	}
	if !ok {
		return ErrForbidden
	}
	_, err := db.ExecContext(ctx, `UPDATE talks SET status = $3 WHERE id = $1 AND status = $2`, talkID, from, to)
	return err
}
