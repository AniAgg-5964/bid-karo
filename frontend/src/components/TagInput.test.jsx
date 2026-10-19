import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TagInput } from "./TagInput";

describe("TagInput", () => {
  it("adds comma and Enter separated tags without duplicates", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { rerender } = render(
      <TagInput value={[]} onChange={onChange} placeholder="Add a sector" />,
    );

    const input = screen.getByLabelText("Add a sector");
    await user.type(input, "Infrastructure{Enter}");
    expect(onChange).toHaveBeenCalledWith(["Infrastructure"]);

    rerender(<TagInput value={["Infrastructure"]} onChange={onChange} placeholder="Add a sector" />);
    await user.type(screen.getByLabelText("Add a sector"), "Transport,{Enter}");
    expect(onChange).toHaveBeenLastCalledWith(["Infrastructure", "Transport"]);
  });

  it("removes an existing tag through its accessible button", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={["ISO 9001:2015"]} onChange={onChange} placeholder="Add" />);

    await user.click(screen.getByRole("button", { name: "Remove ISO 9001:2015" }));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
