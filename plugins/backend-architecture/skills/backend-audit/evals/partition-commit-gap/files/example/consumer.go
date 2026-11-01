package example
import ("context"; "github.com/segmentio/kafka-go")
func Run(ctx context.Context, r *kafka.Reader, process func(kafka.Message) error) error {
    slots := make(chan struct{}, 8)
    for {
        m, err := r.FetchMessage(ctx); if err != nil { return err }
        slots <- struct{}{}
        go func(m kafka.Message) {
            defer func(){ <-slots }()
            if process(m) == nil { _ = r.CommitMessages(ctx, m) }
        }(m)
    }
}
