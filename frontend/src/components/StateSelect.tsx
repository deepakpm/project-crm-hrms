import { GST_STATES } from '@/lib/gst-states'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

export function StateSelect({
  value,
  onChange,
  id,
}: {
  value: string
  onChange: (code: string) => void
  id?: string
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger id={id} className="w-full">
        <SelectValue placeholder="Select a state" />
      </SelectTrigger>
      <SelectContent>
        {GST_STATES.map((s) => (
          <SelectItem key={s.code} value={s.code}>
            {s.code} - {s.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
