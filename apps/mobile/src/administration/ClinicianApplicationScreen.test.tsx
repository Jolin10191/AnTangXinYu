import { act, create, type ReactTestRenderer } from "react-test-renderer";
import { Pressable, Text, TextInput, View } from "react-native";
import { ClinicianApplicationScreen } from "./ClinicianApplicationScreen";
import type { User } from "../api/types";

void [Pressable, Text, TextInput, View];
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: jest.requireActual("react-native").View,
}));
const patient: User = {
  id: "doctor",
  username: "doctor",
  role: "patient",
  applicationStatus: "pending",
};
const application = {
  id: "request",
  applicant: patient,
  fullName: "申请姓名",
  organization: "申请机构",
  status: "pending" as const,
  createdAt: "2026-10-15T00:00:00Z",
  reviewedAt: null,
  rejectionReason: null,
};

test("approved applicant refreshes current role without creating a new login session", async () => {
  const client = {
    me: jest.fn().mockResolvedValue(patient),
    getOwnClinicianApplication: jest.fn().mockResolvedValue(application),
    submitClinicianApplication: jest.fn(),
    logout: jest.fn(),
  };
  const updated = jest.fn();
  let tree!: ReactTestRenderer;
  await act(async () => {
    tree = create(
      <ClinicianApplicationScreen
        api={client}
        onUserUpdated={updated}
        onSignedOut={jest.fn()}
      />,
    );
  });
  expect(JSON.stringify(tree.toJSON())).toContain("医护申请待审批");
  client.me.mockResolvedValue({
    ...patient,
    role: "clinician",
    applicationStatus: "approved",
  });
  await act(async () => {
    tree.root
      .findAllByProps({ accessibilityLabel: "刷新审批状态" })[0]
      .props.onPress();
  });
  expect(updated).toHaveBeenCalledWith(
    expect.objectContaining({ role: "clinician" }),
  );
  await act(async () => tree.unmount());
});

test("rejected applicant can read reason and resubmit corrected information", async () => {
  const client = {
    me: jest
      .fn()
      .mockResolvedValue({ ...patient, applicationStatus: "rejected" }),
    getOwnClinicianApplication: jest
      .fn()
      .mockResolvedValue({
        ...application,
        status: "rejected",
        rejectionReason: "请补充机构",
      }),
    submitClinicianApplication: jest.fn().mockResolvedValue(application),
    logout: jest.fn(),
  };
  let tree!: ReactTestRenderer;
  await act(async () => {
    tree = create(
      <ClinicianApplicationScreen
        api={client}
        onUserUpdated={jest.fn()}
        onSignedOut={jest.fn()}
      />,
    );
  });
  expect(JSON.stringify(tree.toJSON())).toContain("请补充机构");
  act(() => {
    tree.root
      .findAllByProps({ accessibilityLabel: "重新申请所属机构" })[0]
      .props.onChangeText("已补充机构");
  });
  await act(async () => {
    tree.root
      .findAllByProps({ accessibilityLabel: "重新提交医护申请" })[0]
      .props.onPress();
  });
  expect(client.submitClinicianApplication).toHaveBeenCalledWith(
    "申请姓名",
    "已补充机构",
  );
  await act(async () => tree.unmount());
});
