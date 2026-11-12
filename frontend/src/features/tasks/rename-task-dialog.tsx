import { FormDialog } from "@/components/form-dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function RenameTaskDialog({
  name,
  onSave,
}: {
  name: string;
  onSave: (name: string) => Promise<void>;
}) {
  return (
    <FormDialog
      trigger={<Button variant="outline">Rename task</Button>}
      title="Rename task"
      description="Change the task name. The saved scope is read-only."
      submitLabel="Save name"
      className="sm:max-w-lg"
      onSubmit={(data) => onSave(String(data.get("name")))}
    >
      <label className="field">
        Name
        <Input
          name="name"
          defaultValue={name}
          required
          maxLength={100}
          autoComplete="off"
        />
      </label>
    </FormDialog>
  );
}
