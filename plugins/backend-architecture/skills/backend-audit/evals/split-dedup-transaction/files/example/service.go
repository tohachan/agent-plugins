package example

import (
    "context"
    "database/sql"
    "net/http"
    "time"
)

type Service struct { DB *sql.DB; Client *http.Client }

// The provider status lookup is read-only. Every request uses a bounded context.
func (s *Service) Lookup(ctx context.Context, url string) error {
    ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
    defer cancel()
    req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
    if err != nil { return err }
    res, err := s.Client.Do(req)
    if err != nil { return err }
    defer res.Body.Close()
    return nil
}

// Broker adapter acknowledges only on nil; otherwise it retries.
func (s *Service) Ship(ctx context.Context, eventID string, orderID int64) error {
    tx, err := s.DB.BeginTx(ctx, nil)
    if err != nil { return err }
    defer tx.Rollback()
    res, err := s.DB.ExecContext(ctx, "INSERT INTO inbox(event_id) VALUES($1) ON CONFLICT DO NOTHING", eventID)
    if err != nil { return err }
    n, err := res.RowsAffected()
    if err != nil { return err }
    if n == 0 { return tx.Commit() }
    _, err = tx.ExecContext(ctx, "INSERT INTO shipments(order_id) VALUES($1)", orderID)
    if err != nil { return err }
    return tx.Commit()
}

func New(db *sql.DB) *Service { return &Service{DB: db, Client: &http.Client{}} }
