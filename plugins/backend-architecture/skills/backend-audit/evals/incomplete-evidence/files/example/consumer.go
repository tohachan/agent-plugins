package example
import ("context"; "database/sql")
func Ship(ctx context.Context, db *sql.DB, id int64) error { _,err := db.ExecContext(ctx,"INSERT INTO shipments(order_id) VALUES($1)",id); return err }
