import { act, create, type ReactTestRenderer } from "react-test-renderer";
import { Alert, Pressable, Text, TextInput } from "react-native";
import { ApiError } from "../api/client";
import type { ApiClient } from "../api/client";
import type { HealthProfile, User } from "../api/types";
import { ClinicianScreen, PatientAccessScreen } from "./patient-access-screen";

void [Pressable, Text, TextInput];
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: jest.requireActual("react-native").View,
}));
jest.mock("../health-overview/health-overview-screen", () => ({
  WearableCard: () => null,
  sourceLabel: (value: string) => value,
}));

const patient: User = {
  id: "patient-a",
  username: "患者甲",
  role: "patient",
  fullName: "患者姓名",
};
const clinician: User = {
  id: "clinician-c",
  username: "医生丙",
  role: "clinician",
};
const profile: HealthProfile = {
  personalProfile: {
    sex: null,
    ageYears: 28,
    ageAsOfDate: null,
    heightCm: null,
    weightKg: null,
    residentArea: "测试地区",
    occupation: null,
    scheduleType: null,
    revision: 0,
    updatedAt: "2026-10-15T00:00:00Z",
  },
  healthFacts: [],
  wearableLatest: [],
  heartRateTrend: [],
};

async function press(tree: ReactTestRenderer, title: string) {
  await act(async () => {
    tree.root.findAllByProps({ accessibilityLabel: title })[0].props.onPress();
  });
}

test("clinician clears previously read details when the next query is denied", async () => {
  const api = {
    getPatients: jest
      .fn()
      .mockResolvedValue({ patients: [patient], nextAfter: null }),
    getPatientHealthProfile: jest.fn().mockResolvedValue(profile),
    getPatientWearableDashboard: jest.fn().mockResolvedValue({
      periodStart: "2026-09-15T00:00:00Z",
      periodEnd: "2026-10-15T00:00:00Z",
      sources: [],
    }),
    logout: jest.fn(),
  };
  let tree!: ReactTestRenderer;
  await act(async () => {
    tree = create(
      <ClinicianScreen api={api} user={clinician} onSignedOut={jest.fn()} />,
    );
  });
  expect(JSON.stringify(tree.toJSON())).toContain("患者姓名");
  expect(JSON.stringify(tree.toJSON())).not.toContain("患者甲");
  await press(tree, "查看 患者姓名，账号 ID patient-a");
  expect(JSON.stringify(tree.toJSON())).toContain("测试地区");
  api.getPatientHealthProfile.mockRejectedValueOnce(
    new ApiError("授权已撤销", 403),
  );
  await press(tree, "重新查询患者数据");
  expect(JSON.stringify(tree.toJSON())).not.toContain("测试地区");
  expect(JSON.stringify(tree.toJSON())).toContain("授权已撤销");
  await act(async () => {
    tree.unmount();
  });
});

test("researcher screen does not request patient data", async () => {
  const api = {
    getPatients: jest.fn(),
    getPatientHealthProfile: jest.fn(),
    getPatientWearableDashboard: jest.fn(),
    logout: jest.fn(),
  };
  let tree!: ReactTestRenderer;
  await act(async () => {
    tree = create(
      <ClinicianScreen
        api={api}
        user={{ ...clinician, role: "researcher" }}
        onSignedOut={jest.fn()}
      />,
    );
  });
  expect(api.getPatients).not.toHaveBeenCalled();
  expect(JSON.stringify(tree.toJSON())).toContain("此账号没有患者资料访问权限");
  await act(async () => {
    tree.unmount();
  });
});

test("patient verifies clinician, grants read access and revokes it", async () => {
  const grant = {
    id: "grant-1",
    clinician,
    grantedAt: "2026-10-15T00:00:00Z",
    revokedAt: null,
    available: true,
  };
  const api = {
    getPatientGrants: jest.fn().mockResolvedValue([]),
    resolveClinician: jest.fn().mockResolvedValue(clinician),
    grantPatientAccess: jest.fn().mockResolvedValue(grant),
    revokePatientAccess: jest.fn().mockResolvedValue(undefined),
    me: jest.fn().mockResolvedValue(patient),
    updateAccountName: jest
      .fn()
      .mockResolvedValue({ ...patient, fullName: "新姓名" }),
  };
  let tree!: ReactTestRenderer;
  await act(async () => {
    tree = create(
      <PatientAccessScreen
        api={api as unknown as ApiClient}
        onClose={jest.fn()}
      />,
    );
  });
  await act(async () => {
    tree.root
      .findAllByProps({ accessibilityLabel: "我的姓名" })[0]
      .props.onChangeText("新姓名");
  });
  await press(tree, "保存姓名");
  expect(api.updateAccountName).toHaveBeenCalledWith("新姓名");
  await act(async () => {
    tree.root
      .findAllByProps({ accessibilityLabel: "医护完整用户名" })[0]
      .props.onChangeText("医生丙");
  });
  await press(tree, "核对医护账号");
  expect(api.resolveClinician).toHaveBeenCalledWith("医生丙");
  await press(tree, "确认授权");
  expect(api.grantPatientAccess).toHaveBeenCalledWith(clinician.id);
  const alert = jest.spyOn(Alert, "alert");
  await press(tree, "撤销 医生丙 的授权");
  const confirm = alert.mock.calls[0][2]?.find(
    (item) => item.text === "撤销授权",
  );
  await act(async () => {
    confirm?.onPress?.();
  });
  expect(api.revokePatientAccess).toHaveBeenCalledWith("grant-1");
  expect(JSON.stringify(tree.toJSON())).toContain("已撤销授权");
  alert.mockRestore();
  await act(async () => {
    tree.unmount();
  });
});
