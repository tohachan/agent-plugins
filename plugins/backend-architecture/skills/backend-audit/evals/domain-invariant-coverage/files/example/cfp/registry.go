package cfp

// Role is a caller's role.
type Role string

const (
	Speaker      Role = "speaker"
	ProgramChair Role = "program_chair"
	Organizer    Role = "organizer"
	System       Role = "system"
)

// Actions is the authorization registry: every operation and the roles it admits.
var Actions = map[string][]Role{
	"talk.submit":      {Speaker},
	"talk.withdraw":    {Speaker},
	"talk.accept":      {ProgramChair, Organizer},
	"talk.bulk_accept": {Organizer},
	"talk.import":      {Organizer},
	"talk.move":        {ProgramChair},
	"schedule.publish": {Organizer},
	"speaker.import":   {System},
}

// Allowed reports whether role may take action.
func Allowed(action string, role Role) bool {
	for _, r := range Actions[action] {
		if r == role {
			return true
		}
	}
	return false
}
