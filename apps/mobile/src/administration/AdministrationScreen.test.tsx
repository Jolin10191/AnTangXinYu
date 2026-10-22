import { act, create, type ReactTestRenderer } from "react-test-renderer";
import { Pressable, Text, TextInput, View } from "react-native";
import { AdministrationScreen } from "./AdministrationScreen";
import type { User } from "../api/types";

void [Pressable, Text, TextInput, View];
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: jest.requireActual("react-native").View,
}));
const developer: User = {
  id: "developer",
  username: "researcher",
  role: "researcher",
};
const counts = {
  totalUsers: 8,
  patients: 5,
  clinicians: 2,
  collaborators: 1,
  pendingApplications: 1,
};
const applicant: User = {
  id: "applicant",
  username: "doc_applicant",
  role: "patient",
  fullName: "医护姓名",
};
const application = {
  id: "request",
  applicant,
  fullName: "医护姓名",
  organization: "联调医院",
  status: "pending" as const,
  createdAt: "2026-10-15T00:00:00Z",
  reviewedAt: null,
  rejectionReason: null,
};

function api() {
  return {
    getAdminOverview: jest.fn().mockResolvedValue(counts),
    getClinicianApplications: jest
      .fn()
      .mockResolvedValue({ applications: [application], nextAfter: null }),
    reviewClinicianApplication: jest
      .fn()
      .mockResolvedValue({ ...application, status: "approved" }),
    getClinicians: jest
      .fn()
      .mockResolvedValue({ patients: [], nextAfter: null }),
    createClinician: jest
      .fn()
      .mockResolvedValue({ ...applicant, role: "clinician" }),
    assignClinician: jest
      .fn()
      .mockResolvedValue({ ...applicant, role: "clinician" }),
    logout: jest.fn().mockResolvedValue(undefined),
  };
}
async function press(tree: ReactTestRenderer, label: string) {
  await act(async () => {
    tree.root.findAllByProps({ accessibilityLabel: label })[0].props.onPress();
  });
}

test("developer sees real account totals and distribution", async () => {
  const client = api();
  let tree!: ReactTestRenderer;
  await act(async () => {
    tree = create(
      <AdministrationScreen
        api={client}
        user={developer}
        onSignedOut={jest.fn()}
      />,
    );
  });
  expect(client.getAdminOverview).toHaveBeenCalled();
  expect(
    tree.root.findAllByProps({ accessibilityLabel: "总用户：8" }).length,
  ).toBeGreaterThan(0);
  expect(
    tree.root.findAllByProps({ accessibilityLabel: "医护人员：2" }).length,
  ).toBeGreaterThan(0);
  expect(
    tree.root.findAllByProps({ accessibilityLabel: "开发协作者：1" }).length,
  ).toBeGreaterThan(0);
  expect(client.getClinicianApplications).not.toHaveBeenCalled();
  await act(async () => tree.unmount());
});

test("developer approves a pending application and refreshes counts", async () => {
  const client = api();
  let tree!: ReactTestRenderer;
  await act(async () => {
    tree = create(
      <AdministrationScreen
        api={client}
        user={developer}
        onSignedOut={jest.fn()}
      />,
    );
  });
  await press(tree, "医护审批");
  expect(JSON.stringify(tree.toJSON())).toContain("联调医院");
  client.getClinicianApplications.mockResolvedValue({
    applications: [],
    nextAfter: null,
  });
  await press(tree, "通过 医护姓名 的申请");
  expect(client.reviewClinicianApplication).toHaveBeenCalledWith(
    "request",
    "approve",
  );
  expect(client.getAdminOverview.mock.calls.length).toBeGreaterThan(2);
  expect(JSON.stringify(tree.toJSON())).toContain("当前没有此状态的申请");
  await act(async () => tree.unmount());
});

test("developer creates and adds clinician accounts", async () => {
  const client = api();
  let tree!: ReactTestRenderer;
  await act(async () => {
    tree = create(
      <AdministrationScreen
        api={client}
        user={developer}
        onSignedOut={jest.fn()}
      />,
    );
  });
  await press(tree, "医护账号");
  act(() => {
    tree.root
      .findAllByProps({ accessibilityLabel: "新医护姓名" })[0]
      .props.onChangeText("医护姓名");
    tree.root
      .findAllByProps({ accessibilityLabel: "新医护用户名" })[0]
      .props.onChangeText("new_doctor");
    tree.root
      .findAllByProps({ accessibilityLabel: "新医护密码" })[0]
      .props.onChangeText("safe-password");
  });
  await press(tree, "创建医护账号");
  expect(client.createClinician).toHaveBeenCalledWith(
    "new_doctor",
    "safe-password",
    "医护姓名",
  );
  expect(
    tree.root.findAllByProps({ accessibilityLabel: "新医护密码" })[0].props
      .value,
  ).toBe("");
  act(() => {
    tree.root
      .findAllByProps({ accessibilityLabel: "已有账号用户名" })[0]
      .props.onChangeText("existing_patient");
  });
  await press(tree, "添加为医护");
  expect(client.assignClinician).toHaveBeenCalledWith("existing_patient");
  await act(async () => tree.unmount());
});
