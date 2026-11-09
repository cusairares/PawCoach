/**
 * IPetRepository interface contract for the frontend.
 * Defines standard operations for pets, schedules, moments, leaderboard, and devices.
 */
export class IPetRepository {
  /** @returns {Promise<Array<Object>>} */
  async getDogs() {
    throw new Error("getDogs() not implemented");
  }

  /**
   * @param {string} dogId
   * @returns {Promise<Object|null>}
   */
  async getDog(dogId) {
    throw new Error("getDog() not implemented");
  }

  /**
   * @param {Object} data
   * @returns {Promise<Object>}
   */
  async createDog(data) {
    throw new Error("createDog() not implemented");
  }

  /**
   * @param {string} dogId
   * @param {Object} patch
   * @returns {Promise<Object>}
   */
  async updateDog(dogId, patch) {
    throw new Error("updateDog() not implemented");
  }

  /**
   * @param {string} dogId
   * @returns {Promise<{ok: boolean, treatsToday: number, hopper: number}>}
   */
  async giveTreat(dogId) {
    throw new Error("giveTreat() not implemented");
  }

  /**
   * @param {string} dogId
   * @returns {Promise<Object>}
   */
  async addSuccess(dogId) {
    throw new Error("addSuccess() not implemented");
  }

  /**
   * @param {string} dogId
   * @param {string} exerciseId
   * @param {string} stage
   * @returns {Promise<Object>}
   */
  async setExerciseStage(dogId, exerciseId, stage) {
    throw new Error("setExerciseStage() not implemented");
  }

  /**
   * @param {string} [dogId]
   * @returns {Promise<Array<Object>>}
   */
  async getSchedules(dogId) {
    throw new Error("getSchedules() not implemented");
  }

  /**
   * @param {number} scheduleId
   * @param {Object} patch
   * @returns {Promise<Object>}
   */
  async updateSchedule(scheduleId, patch) {
    throw new Error("updateSchedule() not implemented");
  }

  /**
   * @param {number} [limit=5]
   * @param {Array<number>} [excludeIds]
   * @param {string} [clientId]
   * @returns {Promise<Array<Object>>}
   */
  async getRandomMoments(limit, excludeIds, clientId) {
    throw new Error("getRandomMoments() not implemented");
  }

  /**
   * @param {number} momentId
   * @param {string} clientId
   * @param {boolean} liked
   * @returns {Promise<{momentId: number, liked: boolean, likesCount: number}>}
   */
  async setMomentLike(momentId, clientId, liked) {
    throw new Error("setMomentLike() not implemented");
  }

  /**
   * @param {string} [category="score"]
   * @param {string} [scope="city"]
   * @returns {Promise<Array<Object>>}
   */
  async getLeaderboard(category, scope) {
    throw new Error("getLeaderboard() not implemented");
  }

  /** @returns {Promise<{feeder: Object, camera: Object}>} */
  async getDevices() {
    throw new Error("getDevices() not implemented");
  }

  /**
   * @param {string} deviceName
   * @param {Object} patch
   * @returns {Promise<Object>}
   */
  async updateDevice(deviceName, patch) {
    throw new Error("updateDevice() not implemented");
  }
}
