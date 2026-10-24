import { act, create, type ReactTestRenderer } from "react-test-renderer";

import { ProfileScreen } from "./profile-screen";

describe("ProfileScreen", () => {
  it("keeps health profile and dashboard reachable, and reports taps", async () => {
    const opened: string[] = [];
    let renderer: ReactTestRenderer | null = null;
    await act(async () => {
      renderer = create(
        <ProfileScreen
          name="akaa"
          onOpenHealthProfile={() => opened.push("profile")}
          onOpenHealthDashboard={() => opened.push("dashboard")}
          onOpenPsychosocial={() => opened.push("psychosocial")}
          onOpenPatientAccess={() => opened.push("access")}
          onOpenFearRecords={() => opened.push("fear")}
          onOpenSettings={() => opened.push("settings")}
        />,
      );
    });
    const tree = renderer as unknown as ReactTestRenderer;

    const text = JSON.stringify(tree.toJSON());
    expect(text).toContain("健康档案");
    expect(text).toContain("健康看板");
    expect(text).toContain("30 天手环记录");

    const profile = tree.root.findByProps({ accessibilityLabel: "健康档案" });
    await act(async () => {
      profile.props.onPress();
    });
    const dashboard = tree.root.findByProps({ accessibilityLabel: "健康看板" });
    await act(async () => {
      dashboard.props.onPress();
    });
    expect(opened).toEqual(["profile", "dashboard"]);
  });
});
