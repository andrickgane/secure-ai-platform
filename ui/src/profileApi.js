import {
  apiRequest,
} from "./api";


function profilePath(
  profileId
) {
  return encodeURIComponent(
    profileId
  );
}


export function getCustomProfile(
  profileId
) {
  return apiRequest(
    `/profiles/${profilePath(profileId)}`
  );
}


export function getEffectiveProfile(
  profileId
) {
  return apiRequest(
    `/profiles/${profilePath(profileId)}/effective`
  );
}


export function createProfile(
  payload
) {
  return apiRequest(
    "/profiles",
    {
      method: "POST",
      body: JSON.stringify(
        payload
      ),
    }
  );
}


export function updateProfile(
  profileId,
  payload
) {
  return apiRequest(
    `/profiles/${profilePath(profileId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(
        payload
      ),
    }
  );
}


export function cloneProfile(
  profileId,
  payload
) {
  return apiRequest(
    `/profiles/${profilePath(profileId)}/clone`,
    {
      method: "POST",
      body: JSON.stringify(
        payload
      ),
    }
  );
}


export function deleteProfile(
  profileId
) {
  return apiRequest(
    `/profiles/${profilePath(profileId)}`,
    {
      method: "DELETE",
    }
  );
}
